"use client";

import { useState } from "react";

import { cn } from "cn";
import { Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { NameDialog, type NameRequest } from "@/components/name-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";
import { dayIn } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";

import type { TodayTask } from "../../domain/tasks-contract";
import { TodayContext } from "../../model/board-hooks";
import { addTodayTask, setTodayDone, type TodayWords, todayResource, useTodayTasks } from "../../model/today";
import { DeadlineChip } from "../card/deadline-chip";

function useTodayWords(): TodayWords {
  return {
    kanban: useTranslations("kanban"),
    today: useTranslations("kanbanToday"),
    api: useTranslations("kanbanApi"),
    common: useTranslations("common"),
  };
}

function TodayRow({ day, task, words }: { day: string; task: TodayTask; words: TodayWords }) {
  const id = `today-${task.id}`;
  const done = task.status === "done";
  // Просроченная остаётся в Today, пока её не сделают или не перенесут (TK-D11), и показывает свой срок.
  const overdueOn = !done && task.due_on !== null && task.due_on < day ? task.due_on : null;
  return (
    <li className="flex items-center gap-3 pe-4">
      {/* Флажок внутри подписи: вся строка до чипов — одна цель нажатия, без пустого зазора. */}
      <label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 py-3 ps-4 text-sm">
        <Checkbox
          id={id}
          checked={done}
          onCheckedChange={(checked) => void setTodayDone(day, task, checked === true, words)}
        />
        <span dir="auto" className={cn("min-w-0 truncate", done && "text-muted-foreground line-through")}>
          {task.title}
        </span>
      </label>
      {task.status === "in_progress" ? (
        <Badge variant="secondary" className="hidden font-normal sm:inline-flex">
          {words.kanban("kinds.in_progress")}
        </Badge>
      ) : null}
      {overdueOn ? (
        <DeadlineChip
          startsOn={task.starts_on}
          dueOn={overdueOn}
          done={false}
          byLeo={task.leo_fields.includes("due")}
        />
      ) : null}
    </li>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return <p className="rounded-xl border border-dashed p-4 text-center text-muted-foreground text-sm">{children}</p>;
}

function TodayBody({ day }: { day: string }) {
  const words = useTodayWords();
  const tasks = useTodayTasks(day);
  const [request, setRequest] = useState<NameRequest | null>(null);
  const items = tasks.status === "ready" ? tasks.data : [];
  const done = items.filter((task) => task.status === "done").length;

  const addTask = () =>
    setRequest({
      title: words.today("newTask"),
      initial: "",
      submitLabel: words.today("addTask"),
      onSubmit: (title) => void addTodayTask(day, title, words),
    });

  let body: React.ReactNode = <Skeleton className="h-32 rounded-xl" />;
  if (tasks.status === "error")
    body = (
      <Notice>
        {words.today("loadFailed")}{" "}
        <Button variant="link" className="h-auto p-0" onClick={() => void todayResource(day).refresh()}>
          {words.common("actions.retry")}
        </Button>
      </Notice>
    );
  else if (tasks.status === "ready")
    body =
      items.length === 0 ? (
        <Notice>{words.today("empty")}</Notice>
      ) : (
        <TodayContext value={day}>
          <ul className="divide-y overflow-hidden rounded-xl border bg-background shadow-xs">
            {items.map((task) => (
              <TodayRow key={task.id} day={day} task={task} words={words} />
            ))}
          </ul>
        </TodayContext>
      );

  return (
    <section aria-labelledby="tasks-today" className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-4">
        <h2 id="tasks-today" className="flex items-baseline gap-2 text-xl tracking-tight">
          {words.today("heading")}
          {tasks.status === "ready" ? (
            <span className="text-muted-foreground text-sm tabular-nums">
              {words.today("progress", { done, total: items.length })}
            </span>
          ) : null}
        </h2>
        <Button variant="outline" size="sm" onClick={addTask} disabled={tasks.status !== "ready"}>
          <Plus data-icon="inline-start" />
          {words.today("newTask")}
        </Button>
      </div>
      {body}
      <NameDialog request={request} onClose={() => setRequest(null)} />
    </section>
  );
}

/** Today человека (TK-D11) в его профильный день: личные задачи со сроком по этот день и сделанные в него. */
export function TodayTasks() {
  const now = useNow();
  const zone = useTimeZone();
  if (now === null) return <Skeleton className="h-40 rounded-xl" />;
  return <TodayBody day={dayIn(now, zone)} />;
}
