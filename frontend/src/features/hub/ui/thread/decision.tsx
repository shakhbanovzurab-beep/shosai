import { useTranslations } from "next-intl";

import type { ThreadDecision, ThreadDetail } from "../../domain/contract";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";
import { SaidQuote } from "../why/said-quote";

function DecisionCard({ label, decision, muted }: { label: string; decision: ThreadDecision; muted?: boolean }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-lg border p-3">
      <p className="text-muted-foreground text-xs">
        {label} ·{" "}
        {t("thread.decidedAt", { date: say.date(decision.decidedAt), meeting: decision.evidence.meetingTitle })}
      </p>
      <p
        dir="auto"
        className={muted ? "text-pretty text-muted-foreground text-sm line-through" : "text-pretty font-medium text-sm"}
      >
        {decision.text}
      </p>
      <SaidQuote evidence={decision.evidence} />
    </div>
  );
}

/**
 * What was decided, when and where, and how it turned out when that's known. A reversed decision
 * shows both side by side, with dates and sources; an unknown outcome stays unknown.
 */
export function DecisionSection({ detail }: { detail: ThreadDetail }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  const { decision, previousDecision, outcome } = detail;
  if (!decision) return null;
  return (
    <section aria-labelledby="thread-decision" className="flex flex-col gap-3">
      <h3 id="thread-decision" className="flex items-center gap-1.5 font-medium text-muted-foreground text-sm">
        {previousDecision ? <GapIcon kind="contradiction" /> : null}
        {previousDecision ? t("thread.decisionChanged") : t("thread.decision")}
      </h3>
      {previousDecision ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <DecisionCard label={t("thread.previous")} decision={previousDecision} muted />
          <DecisionCard label={t("thread.current")} decision={decision} />
        </div>
      ) : (
        <DecisionCard label={t("thread.decision")} decision={decision} />
      )}
      <div className="flex flex-col gap-0.5 text-sm">
        <span className="text-muted-foreground text-xs">{t("thread.outcome")}</span>
        {outcome ? (
          <p>
            <span dir="auto">{outcome.text}</span>{" "}
            <span className="text-muted-foreground text-xs">· {say.date(outcome.at)}</span>
          </p>
        ) : (
          <p className="text-muted-foreground italic">{t("thread.outcomeUnknown")}</p>
        )}
      </div>
    </section>
  );
}
