import { firstDue, isValidRecurrence } from "../../domain/recurrence";
import type { TaskPatch } from "../../domain/tasks-contract";
import { ME_PERSON, today } from "../seed/builders";
import { jiraRefusal } from "./jira";
import { fail, type Outcome, ok } from "./outcome";
import { demo, now, placementOf, touch, unplace } from "./state";
import { leoFieldsAfter, setStatus } from "./task-rules";
import type { StoredTask } from "./types";
import { pushToWorkspace } from "./workspace-bridge";

/* Задача из панели: поля по присутствию (`null` очищает), правила TK-D12, удаление сразу (TK-D6). */

/** Чего нельзя задаче Jira (KG-D8): всё, что Jira не узнает. */
function jiraProblem(task: StoredTask, patch: TaskPatch) {
  if (!task.jira) return null;
  const board = placementOf(task.id)?.board;
  const refusal = board ? jiraRefusal(board, false) : null;
  if (refusal) return refusal;
  const unsupported =
    (patch.starts_on !== undefined && patch.starts_on !== null) ||
    (patch.recurrence !== undefined && patch.recurrence !== null) ||
    patch.cover_attachment_id !== undefined ||
    patch.description !== undefined ||
    patch.assignee_id !== undefined ||
    patch.assignee_name !== undefined;
  return unsupported ? "jira_unsupported" : null;
}

function assigneeProblem(task: StoredTask, patch: TaskPatch) {
  if (task.space) return patch.assignee_name !== undefined ? "validation_error" : null;
  return patch.assignee_id !== undefined ? "validation_error" : null;
}

/** Значение поля после изменения: присланное (и `null`, который очищает) или прежнее. */
function after<K extends keyof TaskPatch & keyof StoredTask>(task: StoredTask, patch: TaskPatch, key: K) {
  return Object.hasOwn(patch, key) ? ((patch[key] ?? null) as StoredTask[K]) : task[key];
}

function datesOf(task: StoredTask, patch: TaskPatch) {
  const due_on = after(task, patch, "due_on");
  // Без срока нет и начала диапазона.
  const starts_on = due_on === null ? null : after(task, patch, "starts_on");
  return { due_on, starts_on };
}

export function patchTask(task: StoredTask, patch: TaskPatch): Outcome<StoredTask> {
  const problem = jiraProblem(task, patch) ?? assigneeProblem(task, patch);
  if (problem) return fail(problem);
  let { due_on, starts_on } = datesOf(task, patch);
  if (starts_on !== null && due_on !== null && starts_on > due_on) return fail("range_invalid");
  const recurrence = after(task, patch, "recurrence");
  if (recurrence && !isValidRecurrence(recurrence)) return fail("recurrence_invalid");
  if (recurrence && due_on === null) due_on = firstDue(recurrence, today());
  if (patch.cover_attachment_id) {
    const attachment = demo()
      .attachments.get(task.id)
      ?.find((a) => a.id === patch.cover_attachment_id);
    if (!attachment) return fail("attachment_not_found");
    if (!attachment.image) return fail("cover_not_image");
  }

  task.leo_fields = leoFieldsAfter(task, patch);
  if (patch.title !== undefined) task.title = patch.title;
  if (patch.description !== undefined) task.description = patch.description;
  if (patch.priority !== undefined) task.priority = patch.priority;
  if (patch.cover_attachment_id !== undefined) task.cover_attachment_id = patch.cover_attachment_id;
  if (patch.assignee_name !== undefined)
    task.assignee = patch.assignee_name === null ? null : { user_id: null, name: patch.assignee_name };
  if (patch.assignee_id !== undefined)
    task.assignee =
      patch.assignee_id === null
        ? null
        : {
            user_id: patch.assignee_id,
            name: patch.assignee_id === ME_PERSON.user_id ? ME_PERSON.name : patch.assignee_id,
          };
  task.due_on = due_on;
  task.starts_on = starts_on;
  task.recurrence = recurrence;
  pushToWorkspace(task, {
    title: patch.title,
    due_on: patch.due_on !== undefined ? due_on : undefined,
    assignee_id: patch.assignee_id,
  });
  if (patch.status !== undefined) setStatus(task, patch.status);
  task.updated_at = now();
  const board = placementOf(task.id)?.board;
  if (board) touch(board);
  return ok(task);
}

/** Удаление всех или ни одной: чужую задачу пространства и задачу Jira здесь не удалить. */
export function deleteTasks(ids: string[]): Outcome<null> {
  const d = demo();
  for (const id of ids) {
    const task = d.tasks.get(id);
    if (!task) return fail("task_not_found");
    if (task.space || task.jira) return fail("task_not_deletable");
  }
  for (const id of ids) {
    const board = unplace(id);
    if (board) touch(board);
    d.tasks.delete(id);
    for (const map of [d.values, d.subtasks, d.comments, d.attachments]) map.delete(id);
  }
  return ok(null);
}
