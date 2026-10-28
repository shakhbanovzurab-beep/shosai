import { ApiError } from "@/lib/api/errors";

/**
 * Почему studio отказал в запросе: коды бэкенда для `/v1/studio/*` (шаг 8) и общие коды, которые эти маршруты
 * могут вернуть. Экран называет их словами каталога `studioApi`; любой другой код остаётся текстом сервера с id
 * запроса для поддержки.
 */
export const STUDIO_PROBLEMS = [
  "validation_failed",
  "prompt_name_required",
  "prompt_not_found",
  "prompt_limit_reached",
  "prompt_over_budget",
  "prompt_for_other_role",
  "skill_not_installed",
  "model_not_on_plan",
  "model_cant_do_role",
  "max_tokens_range",
  "entitlements_unavailable",
  "idempotency_key_reused",
] as const;

export type StudioProblemCode = (typeof STUDIO_PROBLEMS)[number];

export type StudioProblem = { code: StudioProblemCode; params: Readonly<Record<string, unknown>> };

/** Известный отказ за ошибкой или null для любой другой. */
export function studioProblemOf(error: unknown): StudioProblem | null {
  if (!(error instanceof ApiError)) return null;
  const code = STUDIO_PROBLEMS.find((known) => known === error.code);
  return code === undefined ? null : { code, params: error.params };
}

/** Число параметра отказа; сервер присылает числа, но тип параметров — любой. */
export const numberParam = (params: StudioProblem["params"], name: string) => Number(params[name] ?? 0);
