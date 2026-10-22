import { ApiError } from "@/lib/api/errors";

/*
 * Почему API досок и задач отказал: коды ADR 0008 (план tasks §3.3, §3.8). Кабинет называет их на языке
 * человека; любой другой код показывает текст сервера и id запроса для поддержки.
 */
export const KANBAN_PROBLEMS = [
  "board_not_found",
  "column_not_found",
  "task_not_found",
  "board_changed",
  "board_full",
  "boards_full",
  "board_columns_full",
  "last_column_of_kind",
  "managed_in_jira",
  "reconnect_jira",
  "first_sync",
  "connect_jira_first",
  "jira_board_unavailable",
  "jira_board_synced",
  "not_jira_board",
  "jira_not_incoming",
  "jira_unsupported",
  "timer_not_set",
  "workspace_task_copy",
  "task_not_deletable",
  "validation_error",
  "name_required",
  "name_too_long",
  "title_required",
  "title_too_long",
  "description_too_long",
  "comment_too_long",
  "range_invalid",
  "recurrence_invalid",
  "subtask_not_found",
  "subtasks_full",
  "comment_not_found",
  "not_comment_author",
  "attachment_not_found",
  "attachments_full",
  "cover_not_image",
  "sticker_not_found",
  "sticker_not_on_board",
  "system_sticker",
  "board_stickers_full",
  "stickers_full",
  "states_full",
  "state_not_found",
  "value_kind_mismatch",
  "upload_not_claimable",
  "upload_too_large",
  "storage_limit",
  "storage_not_included",
  "file_not_found",
] as const;

export type KanbanProblem = (typeof KANBAN_PROBLEMS)[number];

/** Известная причина отказа или null, если код кабинету не знаком. */
export function kanbanProblemOf(error: unknown): KanbanProblem | null {
  if (!(error instanceof ApiError)) return null;
  return KANBAN_PROBLEMS.find((problem) => problem === error.code) ?? null;
}
