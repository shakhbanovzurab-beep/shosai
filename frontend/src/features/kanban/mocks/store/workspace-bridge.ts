import type { MyTask } from "@/features/workspace/domain/personal-contract";
import { myTasks, updateMyTask } from "@/features/workspace/mocks/personal";

import type { TaskPatch } from "../../domain/tasks-contract";
import { MANUAL, ME_PERSON, minutesAgo, seedTask } from "../seed/builders";
import { demo, now, unplace } from "./state";
import type { StoredTask } from "./types";

/*
 * Задачи пространств, назначенные человеку, живут в моках пространства (одно хранилище задач, SM-3); здесь у
 * них только то, чего у пространства нет: место на доске, подзадачи, комментарии, вложения, значения полей.
 * Заголовок, статус, срок и исполнитель читаются оттуда при каждом чтении доски и пишутся туда.
 */

function fromWorkspace(task: MyTask, existing: StoredTask | undefined): StoredTask {
  const base =
    existing ??
    seedTask(task.id, task.title, "", {
      created_at: task.created_at,
      source: task.meeting_id
        ? {
            kind: "meeting",
            meeting: { id: task.meeting_id, title: task.meeting_title ?? "", started_at: task.created_at },
            finding: null,
            chat: null,
          }
        : MANUAL,
    });
  const completed_at = task.status === "done" ? (base.completed_at ?? minutesAgo(60)) : null;
  return {
    ...base,
    title: task.title,
    status: task.status,
    due_on: task.due_on,
    starts_on: task.due_on === null ? null : base.starts_on,
    assignee: { user_id: ME_PERSON.user_id, name: ME_PERSON.name },
    space: {
      workspace_id: task.workspace.id,
      workspace_slug: task.workspace.slug,
      workspace_name: task.workspace.name,
    },
    completed_at,
  };
}

/** Привести задачи пространств к тому, что сейчас назначено человеку; ушедшие снимаются с досок. */
export function syncWorkspaceTasks() {
  const d = demo();
  const mine = new Map(myTasks().map((task) => [task.id, task]));
  for (const task of mine.values()) d.tasks.set(task.id, fromWorkspace(task, d.tasks.get(task.id)));
  for (const task of d.tasks.values()) if (task.space && !mine.has(task.id)) unplace(task.id);
  return mine;
}

/** Изменение задачи пространства из канбана — то же изменение в пространстве. */
export function pushToWorkspace(task: StoredTask, patch: TaskPatch) {
  if (!task.space) return;
  updateMyTask(task.space.workspace_id, task.id, {
    status: patch.status,
    title: patch.title,
    due_on: patch.due_on,
    assignee_id: patch.assignee_id,
  });
  task.updated_at = now();
}
