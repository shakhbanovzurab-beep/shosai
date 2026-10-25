"use client";

import { toast } from "sonner";
import type { useTranslations } from "use-intl";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { tasksApi } from "../api/tasks-api";
import type { TaskStatus, TodayTask } from "../domain/tasks-contract";
import { type ApiWords, type CommonWords, describeProblem, type KanbanWords } from "./words";

/*
 * Today (TK-D11): открытые личные задачи со сроком по профильный день человека и сделанные в этот день. Список
 * на каждый день свой, поэтому в полночь виджет читает новый. Изменения видны сразу и откатываются при отказе.
 */

export type TodayWords = {
  kanban: KanbanWords;
  today: ReturnType<typeof useTranslations<"kanbanToday">>;
  api: ApiWords;
  common: CommonWords;
};

const lists = new Map<string, PollingResource<TodayTask[]>>();

export function todayResource(day: string) {
  const existing = lists.get(day);
  if (existing) return existing;
  const created = inDomain(
    "tasks",
    createPollingResource(() => tasksApi.today(day).then((list) => list.items)),
  );
  lists.set(day, created);
  return created;
}

export const useTodayTasks = (day: string) => usePollingResource(todayResource(day));

const rowOf = ({ id, title, status, starts_on, due_on, recurring, leo_fields }: TodayTask): TodayTask => ({
  id,
  title,
  status,
  starts_on,
  due_on,
  recurring,
  leo_fields,
});

function replace(day: string, id: string, change: (task: TodayTask) => TodayTask) {
  todayResource(day).update((items) => items.map((task) => (task.id === id ? change(task) : task)));
}

/** Личная задача со сроком в этот день — так её добавляет Today; ключ не даёт повтору создать вторую. */
export async function addTodayTask(day: string, title: string, words: TodayWords) {
  try {
    const created = await tasksApi.create({ title, description: "", status: "todo", due_on: day }, crypto.randomUUID());
    todayResource(day).update((items) => [...items, rowOf(created)]);
  } catch (error) {
    toast.error(words.kanban("errors.addTask"), { description: describeProblem(error, words.api) });
  }
}

async function changeStatus(day: string, task: TodayTask, status: TaskStatus, words: TodayWords) {
  replace(day, task.id, (current) => ({ ...current, status }));
  try {
    const saved = await tasksApi.patch(task.id, { status });
    replace(day, task.id, () => rowOf(saved));
    // Сделанная повторяющаяся задача рождает следующую — она может прийтись на этот же день.
    if (task.recurring && status === "done") void todayResource(day).reload();
    return true;
  } catch (error) {
    replace(day, task.id, (current) => ({ ...current, status: task.status }));
    toast.error(words.kanban("errors.saveChange"), { description: describeProblem(error, words.api) });
    return false;
  }
}

/**
 * Отметка или снятие отметки. Тост отметки предлагает Undo, как задачи пространства; у повторяющейся — нет:
 * следующая задача уже создана, и Undo не вернул бы всё как было.
 */
export async function setTodayDone(day: string, task: TodayTask, done: boolean, words: TodayWords) {
  const status: TaskStatus = done ? "done" : "todo";
  if (task.status === status || !(await changeStatus(day, task, status, words)) || !done) return;
  const undo = task.recurring
    ? undefined
    : {
        label: words.common("actions.undo"),
        onClick: () => void changeStatus(day, { ...task, status }, task.status, words),
      };
  toast.success(words.today("markedDone"), { description: task.title, action: undo });
}
