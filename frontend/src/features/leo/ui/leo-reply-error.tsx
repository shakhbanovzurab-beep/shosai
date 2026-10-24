import { useTranslations } from "use-intl";

import type { LeoFailure } from "../domain/types";

// Коды, у которых есть свои слова; остальные — общая строка «проверьте соединение и попробуйте ещё раз».
const WORDED = new Set([
  "token_limit",
  "consent_required",
  "thread_busy",
  "rate_limited",
  "too_many_runs",
  "agent_busy",
  "not_last_question",
  "thread_not_found",
  "question_invalid",
  "model_unavailable",
  "turn_deadline",
  "process_lost",
]);
const UNAVAILABLE = new Set(["agent_unavailable", "entitlements_unavailable"]);

type FailureKey = Exclude<Parameters<ReturnType<typeof useTranslations<"leo.failure">>>[0], "token_limit">;

/** Почему Leo не ответил — словами кода отказа или сбоя хода; сам сбой в текст ответа не пишется. */
export function LeoReplyError({ failure }: { readonly failure?: LeoFailure }) {
  const t = useTranslations("leo");
  const tFailure = useTranslations("leo.failure");
  const code = failure?.code ?? "";
  let text = t("message.replyFailed");
  if (code === "token_limit") text = tFailure("token_limit", { limit: failure?.limit ?? "other" });
  else if (UNAVAILABLE.has(code)) text = tFailure("unavailable");
  else if (WORDED.has(code)) text = tFailure(code as FailureKey);
  return (
    <p className="text-destructive text-sm" role="alert">
      {text}
    </p>
  );
}
