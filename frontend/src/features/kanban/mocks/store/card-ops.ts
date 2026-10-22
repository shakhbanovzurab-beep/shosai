import { NEW_ISSUE_TYPE } from "../../data/jira-catalog";
import { BOARD_OPEN_CARDS_MAX, type CardCreate, type CardPatch } from "../../domain/boards-contract";
import type { JiraIssueRef } from "../../domain/tasks-contract";
import { MANUAL, seedTask } from "../seed/builders";
import { onArrival, onMove } from "./clock-ops";
import { jiraRefusal } from "./jira";
import { fail, type Outcome, ok } from "./outcome";
import { demo, now, placementOf, touch } from "./state";
import { leoFieldsAfter, setStatus } from "./task-rules";
import type { StoredBoard, StoredTask } from "./types";
import { pushToWorkspace } from "./workspace-bridge";

/* Карточки доски: новая задача или копия, переименование, приоритет, перемещение со статусом по виду колонки. */

const openCards = (board: StoredBoard) =>
  board.columns.reduce((sum, c) => sum + c.card_ids.filter((id) => demo().tasks.get(id)?.status !== "done").length, 0);

/** На доске Jira новая задача — новая задача Jira в проекте доски, со следующим ключом. */
function nextIssue(board: StoredBoard): JiraIssueRef | null {
  const link = board.jira;
  if (!link) return null;
  const numbers = board.columns
    .flatMap((c) => c.card_ids)
    .map((id) => Number(demo().tasks.get(id)?.jira?.key.split("-")[1] ?? 0));
  const key = `${link.project_key}-${Math.max(0, ...numbers) + 1}`;
  return { key, url: `https://${link.site}/browse/${key}`, type: NEW_ISSUE_TYPE };
}

function copyOf(source: StoredTask, id: string, title: string): StoredTask {
  const d = demo();
  const values = d.values.get(source.id);
  if (values) d.values.set(id, new Map(values));
  const subtasks = d.subtasks.get(source.id) ?? [];
  d.subtasks.set(
    id,
    subtasks.map((s, i) => ({ id: `${id}-s${i + 1}`, title: s.title, done: false })),
  );
  const created_at = now();
  return {
    ...source,
    id,
    title,
    cover_attachment_id: null,
    leo_fields: [],
    source: MANUAL,
    created_at,
    updated_at: created_at,
    completed_at: null,
    recurred_from_id: null,
    plan_minutes: null,
    fact_minutes: null,
  };
}

export function createCard(board: StoredBoard, request: CardCreate): Outcome<StoredTask> {
  const refusal = jiraRefusal(board, request.copy_of !== undefined);
  if (refusal) return fail(refusal);
  const column = board.columns.find((c) => c.id === request.column_id);
  if (!column) return fail("column_not_found");
  if (column.kind !== "done" && openCards(board) >= BOARD_OPEN_CARDS_MAX) return fail("board_full");
  const id = crypto.randomUUID();
  let task = seedTask(id, request.title, "", { status: column.kind, created_at: now(), updated_at: now() });
  if (request.copy_of) {
    const source = demo().tasks.get(request.copy_of);
    if (!source || placementOf(source.id)?.board !== board) return fail("task_not_found");
    if (source.space) return fail("workspace_task_copy");
    task = { ...copyOf(source, id, request.title), status: column.kind };
  }
  const issue = nextIssue(board);
  if (issue) task = { ...task, id: `jira-${issue.key}`, jira: issue, source: { ...MANUAL, kind: "jira" } };
  task.completed_at = task.status === "done" ? now() : null;
  demo().tasks.set(task.id, task);
  column.card_ids.splice(Math.max(0, Math.min(request.position, column.card_ids.length)), 0, task.id);
  onArrival(board, task.id, column.id);
  touch(board);
  return ok(task);
}

export function patchCard(board: StoredBoard, taskId: string, patch: CardPatch): Outcome<StoredTask> {
  const refusal = jiraRefusal(board, false);
  if (refusal) return fail(refusal);
  const at = placementOf(taskId);
  const task = demo().tasks.get(taskId);
  if (!at || at.board !== board || !task) return fail("task_not_found");
  if (patch.column_id !== undefined) {
    const target = board.columns.find((c) => c.id === patch.column_id);
    if (!target) return fail("column_not_found");
    at.column.card_ids.splice(at.index, 1);
    target.card_ids.splice(Math.max(0, Math.min(patch.position ?? 0, target.card_ids.length)), 0, taskId);
    setStatus(task, target.kind);
    onMove(board, taskId, at.column.id, target.id);
  }
  if (patch.priority !== undefined) {
    task.leo_fields = leoFieldsAfter(task, { priority: patch.priority });
    task.priority = patch.priority;
  }
  if (patch.title !== undefined) {
    task.title = patch.title;
    pushToWorkspace(task, { title: patch.title });
  }
  task.updated_at = now();
  touch(board);
  return ok(task);
}
