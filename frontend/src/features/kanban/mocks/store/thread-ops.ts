import {
  type CommentsPage,
  SUBTASKS_MAX,
  type Subtask,
  type SubtaskCreate,
  type SubtaskPatch,
} from "../../domain/tasks-contract";
import { ME_PERSON } from "../seed/builders";
import { fail, type Outcome, ok } from "./outcome";
import { commentOf } from "./present";
import { demo, now, touchTask } from "./state";
import type { StoredComment, StoredTask } from "./types";

/* Подзадачи и комментарии задачи (KG-D2, TK-D12): у задачи Jira их нет (KG-D8). */

const clamp = (value: number, max: number) => Math.max(0, Math.min(value, max));

function listOf(task: StoredTask) {
  const d = demo();
  const list = d.subtasks.get(task.id) ?? [];
  d.subtasks.set(task.id, list);
  return list;
}

export function createSubtask(task: StoredTask, request: SubtaskCreate): Outcome<Subtask> {
  if (task.jira) return fail("jira_unsupported");
  const list = listOf(task);
  if (list.length >= SUBTASKS_MAX) return fail("subtasks_full");
  const subtask: Subtask = { id: crypto.randomUUID(), title: request.title, done: false };
  list.splice(clamp(request.position ?? list.length, list.length), 0, subtask);
  task.updated_at = now();
  touchTask(task.id);
  return ok(subtask);
}

export function patchSubtask(task: StoredTask, id: string, patch: SubtaskPatch): Outcome<Subtask> {
  const list = listOf(task);
  const subtask = list.find((s) => s.id === id);
  if (!subtask) return fail("subtask_not_found");
  if (patch.title !== undefined) subtask.title = patch.title;
  if (patch.done !== undefined) subtask.done = patch.done;
  if (patch.position !== undefined) {
    list.splice(list.indexOf(subtask), 1);
    list.splice(clamp(patch.position, list.length), 0, subtask);
  }
  task.updated_at = now();
  touchTask(task.id);
  return ok(subtask);
}

export function deleteSubtask(task: StoredTask, id: string): Outcome<null> {
  const list = listOf(task);
  const index = list.findIndex((s) => s.id === id);
  if (index < 0) return fail("subtask_not_found");
  list.splice(index, 1);
  touchTask(task.id);
  return ok(null);
}

/*
 * Комментарии: страницы новыми вперёд. Курсор — непрозрачный ключ последнего отданного (время и id), а не сдвиг:
 * новый комментарий не сдвигает следующую страницу, и ничего не повторяется.
 */

const keyOf = (comment: StoredComment) => `${comment.created_at}|${comment.id}`;
const encodeCursor = (key: string) => btoa(`c:${key}`);
function decodeCursor(cursor: string | null): string | null {
  if (!cursor) return null;
  try {
    const decoded = atob(cursor);
    return decoded.startsWith("c:") ? decoded.slice(2) : null;
  } catch {
    return null;
  }
}

export function commentsPage(task: StoredTask, cursor: string | null, limit: number): CommentsPage {
  const newest = (demo().comments.get(task.id) ?? []).toSorted((a, b) => keyOf(b).localeCompare(keyOf(a)));
  const after = decodeCursor(cursor);
  const older = after === null ? newest : newest.filter((comment) => keyOf(comment) < after);
  const items = older.slice(0, limit);
  const last = items.at(-1);
  return {
    items: items.map(commentOf),
    next_cursor: older.length > limit && last ? encodeCursor(keyOf(last)) : null,
  };
}

/** Повтор с тем же `Idempotency-Key` отвечает тем же комментарием. */
const byKey = new Map<string, StoredComment>();

export function createComment(task: StoredTask, body: string, key: string | null): Outcome<StoredComment> {
  if (task.jira) return fail("jira_unsupported");
  const repeated = key ? byKey.get(key) : undefined;
  if (repeated) return ok(repeated);
  const comment: StoredComment = {
    id: crypto.randomUUID(),
    author: ME_PERSON,
    body,
    created_at: now(),
    edited_at: null,
  };
  const d = demo();
  d.comments.set(task.id, [...(d.comments.get(task.id) ?? []), comment]);
  if (key) byKey.set(key, comment);
  touchTask(task.id);
  return ok(comment);
}

function ownComment(task: StoredTask, id: string): Outcome<StoredComment> {
  const comment = demo()
    .comments.get(task.id)
    ?.find((c) => c.id === id);
  if (!comment) return fail("comment_not_found");
  return comment.author.user_id === ME_PERSON.user_id ? ok(comment) : fail("not_comment_author");
}

export function editComment(task: StoredTask, id: string, body: string): Outcome<StoredComment> {
  const found = ownComment(task, id);
  if (found.ok) {
    found.value.body = body;
    found.value.edited_at = now();
  }
  return found;
}

export function deleteComment(task: StoredTask, id: string): Outcome<null> {
  const found = ownComment(task, id);
  if (!found.ok) return found;
  const d = demo();
  d.comments.set(
    task.id,
    (d.comments.get(task.id) ?? []).filter((c) => c.id !== id),
  );
  touchTask(task.id);
  return ok(null);
}
