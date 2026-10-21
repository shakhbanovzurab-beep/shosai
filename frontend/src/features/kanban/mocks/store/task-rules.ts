import { addMyTask } from "@/features/workspace/mocks/personal";

import { nextDue, shiftedStart } from "../../domain/recurrence";
import { leoFieldsAfter as leoFieldsLeft } from "../../domain/task-rules";
import type { LeoField, TaskPatch, TaskStatus } from "../../domain/tasks-contract";
import { today } from "../seed/builders";
import { demo, firstColumnOf, now, placementOf, touch } from "./state";
import type { StoredTask } from "./types";
import { pushToWorkspace } from "./workspace-bridge";

/* Правила, общие для изменений задачи с доски и из панели. */

/** Какие метки Лео остаются после изменения (KG-D10) — то же правило, что видит панель. */
export const leoFieldsAfter = (task: StoredTask, patch: TaskPatch): LeoField[] => leoFieldsLeft(task.leo_fields, patch);

/** Следующая задача повторяющейся (KG-D5): один раз на закрытую, по расписанию после её срока. */
function spawnNext(task: StoredTask) {
  const d = demo();
  if (!task.recurrence || !task.due_on) return;
  if ([...d.tasks.values()].some((t) => t.recurred_from_id === task.id)) return;
  const due_on = nextDue(task.recurrence, task.due_on, today());
  const starts_on = shiftedStart(task.starts_on, task.due_on, due_on);
  const id = task.space ? addMyTask(task.space.workspace_id, { title: task.title, due_on }) : crypto.randomUUID();
  if (!id) return;
  const created_at = now();
  d.tasks.set(id, {
    ...task,
    id,
    status: "todo",
    due_on,
    starts_on,
    cover_attachment_id: null,
    leo_fields: [],
    created_at,
    updated_at: created_at,
    completed_at: null,
    recurred_from_id: task.id,
  });
  task.recurrence = null;
  const values = d.values.get(task.id);
  if (values) d.values.set(id, new Map(values));
  const subtasks = d.subtasks.get(task.id) ?? [];
  d.subtasks.set(
    id,
    subtasks.map((s, i) => ({ id: `${id}-s${i + 1}`, title: s.title, done: false })),
  );
  const at = placementOf(task.id);
  const column = at ? firstColumnOf(at.board, "todo") : null;
  if (at && column) {
    column.card_ids.unshift(id);
    touch(at.board);
  }
}

/** Новый статус задачи: время закрытия, следующая повторяющаяся, то же изменение в пространстве. */
export function setStatus(task: StoredTask, status: TaskStatus) {
  if (task.status === status) return;
  task.status = status;
  task.completed_at = status === "done" ? now() : null;
  task.updated_at = now();
  pushToWorkspace(task, { status });
  if (status === "done") spawnNext(task);
}
