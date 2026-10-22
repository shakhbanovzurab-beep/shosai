import type { z } from "zod";

import { membership } from "@/features/workspace/mocks/demo-store";
import { JsonResponse } from "@/mocks/runtime";

import type { ChatsProblem } from "../../domain/problems";
import type { Outcome } from "../store/outcome";

/*
 * Ответы моков в форме бэкенда: отказ — конверт ADR 0008 с кодом, который кабинет называет на языке человека;
 * статус выводится из кода, как его отдал бы сервер. Доступ — как у ворот пространства: не участник — 404,
 * приостановленное — 423, изменение не админом — 403.
 */

const STATUS: Partial<Record<ChatsProblem, number>> = {
  workspace_not_found: 404,
  chat_not_found: 404,
  installation_not_found: 404,
  code_not_found: 404,
  item_not_found: 404,
  digest_not_found: 404,
  not_workspace_admin: 403,
  workspace_suspended: 423,
  project_not_found: 422,
  data_notice_required: 422,
  retention_invalid: 422,
  mode_invalid: 422,
  validation_error: 422,
};

type Params = Record<string, string | number | string[]>;

/** Отказ с кодом; всё, чего нет в таблице, — 409, как конфликт с состоянием. */
export function refuse(code: ChatsProblem, params?: Params) {
  const error = { code, request_id: `demo-${crypto.randomUUID()}`, ...(params ? { params } : {}) };
  return JsonResponse.json({ error, detail: code }, { status: STATUS[code] ?? 409 });
}

export const json = <T>(body: T, status = 200) => JsonResponse.json<T>(body, { status });
export const noContent = () => new Response(null, { status: 204 });

/** Исход операции хранилища: значение в форме контракта или отказ с его кодом. */
export function answer<T, R>(outcome: Outcome<T>, present: (value: T) => R, status = 200) {
  return outcome.ok ? json(present(outcome.value), status) : refuse(outcome.code, outcome.params);
}

export const answerEmpty = <T>(outcome: Outcome<T>) =>
  outcome.ok ? noContent() : refuse(outcome.code, outcome.params);

/** Тело по схеме — или ответ-отказ, который надо вернуть вместо него. */
export async function bodyOf<S extends z.ZodType>(
  request: Request,
  schema: S,
): Promise<{ data: z.infer<S> } | { refusal: Response }> {
  const parsed = schema.safeParse(await request.json().catch(() => null));
  if (parsed.success) return { data: parsed.data };
  const message = parsed.error.issues[0]?.message ?? "";
  const known = /^[a-z_]+$/.test(message) && message !== "validation_error";
  return { refusal: refuse(known ? (message as ChatsProblem) : "validation_error") };
}

export type Ctx<K extends string> = { params: Promise<Record<K, string>> };

/** Пространство из пути: участник читает, админ (владелец или админ) меняет. */
export async function inWorkspace(
  params: Promise<{ id: string }>,
  need: "member" | "admin",
  run: (workspaceId: string) => Response | Promise<Response>,
) {
  const { id } = await params;
  const found = membership(id);
  if (!found) return refuse("workspace_not_found");
  if (found.data.control.suspended) return refuse("workspace_suspended");
  if (need === "admin" && found.me.role === "member") return refuse("not_workspace_admin");
  return run(id);
}
