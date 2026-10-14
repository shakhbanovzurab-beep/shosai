import { useTranslations } from "use-intl";

import type { Refusal } from "../model/outcome";

/** Почему шаг не удался — словами; номер запроса — когда причину может понять только поддержка. */
export function ProblemMessage({ refusal }: { refusal: Refusal }) {
  const t = useTranslations("identity");
  return (
    <div role="alert" className="flex flex-col gap-1 text-destructive text-sm">
      <p>{t(`problems.${refusal.problem}`)}</p>
      {refusal.problem === "unknown" && refusal.requestId !== null ? (
        <p className="text-muted-foreground text-xs">{t("problems.requestId", { id: refusal.requestId })}</p>
      ) : null}
    </div>
  );
}
