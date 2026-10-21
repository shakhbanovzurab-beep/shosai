import type { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import type { KanbanProblem } from "../../domain/problems";

/*
 * Ответы моков в форме бэкенда: отказ — конверт ADR 0008 с кодом, который кабинет называет на языке человека;
 * статус выводится из кода, как его отдал бы сервер.
 */

const STATUS: Partial<Record<KanbanProblem, number>> = {
  board_not_found: 404,
  column_not_found: 404,
  task_not_found: 404,
  subtask_not_found: 404,
  comment_not_found: 404,
  attachment_not_found: 404,
  sticker_not_found: 404,
  state_not_found: 404,
  file_not_found: 404,
  jira_board_unavailable: 404,
  sticker_not_on_board: 404,
  task_not_deletable: 403,
  not_comment_author: 403,
  storage_not_included: 403,
  upload_too_large: 413,
  storage_limit: 413,
  validation_error: 422,
  name_required: 422,
  name_too_long: 422,
  title_required: 422,
  title_too_long: 422,
  description_too_long: 422,
  comment_too_long: 422,
  range_invalid: 422,
  recurrence_invalid: 422,
  value_kind_mismatch: 422,
};

/** Отказ с кодом; всё, чего нет в таблице, — 409, как конфликт с состоянием. */
export function refuse(code: KanbanProblem) {
  const error = { code, request_id: `demo-${crypto.randomUUID()}` };
  return JsonResponse.json({ error, detail: code }, { status: STATUS[code] ?? 409 });
}

export const json = <T>(body: T, status = 200) => JsonResponse.json<T>(body, { status });
export const noContent = () => new Response(null, { status: 204 });

export const readJson = (request: Request) => request.json().catch(() => null);

/** Код первой нарушенной проверки: сообщение схемы, если это код кабинета, иначе общий `validation_error`. */
function firstIssue(error: z.ZodError): KanbanProblem {
  const message = error.issues[0]?.message ?? "";
  return /^[a-z_]+$/.test(message) && message !== "validation_error" ? (message as KanbanProblem) : "validation_error";
}

/** Тело по схеме — или ответ-отказ, который надо вернуть вместо него. */
export async function bodyOf<S extends z.ZodType>(
  request: Request,
  schema: S,
): Promise<{ data: z.infer<S> } | { refusal: Response }> {
  const parsed = schema.safeParse(await readJson(request));
  return parsed.success ? { data: parsed.data } : { refusal: refuse(firstIssue(parsed.error)) };
}

export type Params<K extends string> = { params: Promise<Record<K, string>> };
