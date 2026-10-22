import { ApiError } from "@/lib/api/errors";

/*
 * Почему API командных чатов отказал: коды ADR 0008 (chats §1.2). Кабинет называет их на языке человека;
 * любой другой код показывает текст сервера и id запроса для поддержки.
 */
export const CHATS_PROBLEMS = [
  "workspace_not_found",
  "workspace_suspended",
  "chat_not_found",
  "installation_not_found",
  "code_not_found",
  "item_not_found",
  "digest_not_found",
  "project_not_found",
  "not_workspace_admin",
  "data_notice_required",
  "connections_full",
  "rejoin_unsupported",
  "token_expired",
  "channel_already_connected",
  "leo_not_in_channel",
  "item_already_proposed",
  "retention_invalid",
  "mode_invalid",
  "validation_error",
] as const;

export type ChatsProblem = (typeof CHATS_PROBLEMS)[number];

/** Известная причина отказа или null, если код кабинету не знаком. */
export function chatsProblemOf(error: unknown): ChatsProblem | null {
  if (!(error instanceof ApiError)) return null;
  return CHATS_PROBLEMS.find((problem) => problem === error.code) ?? null;
}
