import type { BoardDetail, BoardSummary } from "../../domain/boards-contract";
import { DONE_VISIBLE_DAYS } from "../../domain/boards-contract";
import { type BoardSticker, type StickerValue, SYSTEM_STICKERS } from "../../domain/stickers-contract";
import type { Card, Comment, TaskDetail } from "../../domain/tasks-contract";
import { ME_PERSON } from "../seed/builders";
import { demo, placementOf } from "./state";
import type { StoredBoard, StoredComment, StoredTask } from "./types";

/* Ответы API из хранилища: карточка, доска, задача — по формам контракта. */

const DONE_WINDOW_MS = DONE_VISIBLE_DAYS * 86_400_000;

/** На доске — открытые и закрытые за последние 30 дней (TK-D5). */
export function isShown(task: StoredTask) {
  if (task.status !== "done") return true;
  return task.completed_at !== null && Date.now() - Date.parse(task.completed_at) <= DONE_WINDOW_MS;
}

const customIdsOf = (board: StoredBoard) => new Set(board.stickers.map((sticker) => sticker.id));

function valuesOf(taskId: string, keep: (stickerId: string) => boolean) {
  const values: Record<string, StickerValue> = {};
  for (const [id, value] of demo().values.get(taskId) ?? []) if (keep(id)) values[id] = value;
  return values;
}

export function cardOf(task: StoredTask, board: StoredBoard | null): Card {
  const d = demo();
  const custom = board ? customIdsOf(board) : new Set<string>();
  const subtasks = d.subtasks.get(task.id) ?? [];
  const attachments = d.attachments.get(task.id) ?? [];
  const cover = attachments.find((a) => a.id === task.cover_attachment_id);
  return {
    id: task.id,
    title: task.title,
    status: task.status,
    priority: task.priority,
    starts_on: task.starts_on,
    due_on: task.due_on,
    assignee: task.assignee,
    cover: cover ? { attachment_id: cover.id, preview_url: cover.preview_url } : null,
    values: valuesOf(task.id, (id) => custom.has(id)),
    subtasks_done: subtasks.filter((s) => s.done).length,
    subtasks_total: subtasks.length,
    comment_count: d.comments.get(task.id)?.length ?? 0,
    attachment_count: attachments.length,
    recurring: task.recurrence !== null,
    leo_fields: task.leo_fields,
    space: task.space,
    jira: task.jira,
    can_delete: task.space === null && task.jira === null,
  };
}

/** Поля доски по порядку: системные четыре, затем свои. */
export function stickersOf(board: StoredBoard): BoardSticker[] {
  const system = SYSTEM_STICKERS.map(
    (id): BoardSticker => ({ id, kind: id, name: null, states: [], visible: board.system[id] }),
  );
  const custom = board.stickers.flatMap(({ id, visible }): BoardSticker[] => {
    const sticker = demo().stickers.get(id);
    return sticker ? [{ ...sticker, visible }] : [];
  });
  return [...system, ...custom];
}

const shownIds = (ids: string[]) =>
  ids.filter((id) => {
    const task = demo().tasks.get(id);
    return task !== undefined && isShown(task);
  });

export function summaryOf(board: StoredBoard): BoardSummary {
  return {
    id: board.id,
    name: board.name,
    icon: board.icon,
    jira: board.jira,
    incoming: demo().incoming.board_id === board.id,
    task_count: board.columns.reduce((sum, column) => sum + shownIds(column.card_ids).length, 0),
    created_at: board.created_at,
  };
}

export function boardDetailOf(board: StoredBoard): BoardDetail {
  const tasks = demo().tasks;
  return {
    board: summaryOf(board),
    stickers: stickersOf(board),
    columns: board.columns.map(({ card_ids, ...head }) => ({
      ...head,
      cards: shownIds(card_ids).flatMap((id) => {
        const task = tasks.get(id);
        return task ? [cardOf(task, board)] : [];
      }),
    })),
    revision: board.revision,
  };
}

export function taskDetailOf(task: StoredTask): TaskDetail {
  const d = demo();
  const at = placementOf(task.id);
  const onBoard = at ? customIdsOf(at.board) : new Set<string>();
  const other_values = [...(d.values.get(task.id) ?? [])].flatMap(([id, value]) => {
    const sticker = d.stickers.get(id);
    return sticker && !onBoard.has(id) ? [{ sticker, value }] : [];
  });
  return {
    ...cardOf(task, at?.board ?? null),
    description: task.description,
    recurrence: task.recurrence,
    other_values,
    source: task.source,
    subtasks: d.subtasks.get(task.id) ?? [],
    attachments: d.attachments.get(task.id) ?? [],
    placement: at ? { board_id: at.board.id, column_id: at.column.id } : null,
    created_at: task.created_at,
    updated_at: task.updated_at,
    completed_at: task.completed_at,
  };
}

export const commentOf = (comment: StoredComment): Comment => ({
  ...comment,
  author: { ...comment.author, is_you: comment.author.user_id === ME_PERSON.user_id },
});
