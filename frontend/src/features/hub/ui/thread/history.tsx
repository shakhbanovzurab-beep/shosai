import Link from "next/link";

import { useTranslations } from "next-intl";

import type { ThreadDetail } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import { historySummary, rounds } from "../../domain/phrases";
import { useHubPhrases } from "../shared/phrases";
import { SaidQuote } from "../why/said-quote";

/**
 * The heart of a topic with a history: every meeting it came back to, and what stood in the way that
 * time, in the words said, with a way to that moment of the recording. The sum sits on top.
 */
export function History({ detail }: { detail: ThreadDetail }) {
  const t = useTranslations("hubDetail");
  const hubWords = useTranslations("hub");
  const say = useHubPhrases();
  const list = rounds(detail);
  const summary = historySummary(detail);
  if (list.length === 0) return null;
  return (
    <section aria-labelledby="thread-history" className="flex flex-col gap-3">
      <h3 id="thread-history" className="font-medium text-muted-foreground text-sm">
        {t("thread.history")}
      </h3>
      {summary ? (
        <p className="text-pretty text-sm leading-relaxed">
          {summary.decidedAt
            ? t("thread.summaryDecided", { rounds: summary.rounds, date: say.date(summary.decidedAt) })
            : t("thread.summaryOpen", { rounds: summary.rounds })}
          {summary.blockers.length > 0 ? ` ${t("thread.blockers", { quotes: say.quotes(summary.blockers) })}` : null}
        </p>
      ) : null}
      <ol className="flex flex-col">
        {list.map((round, index) => (
          <li key={`${round.sessionId}-${round.at}-${round.to}`} className="relative flex gap-3 pb-4 last:pb-0">
            <span className="flex flex-col items-center" aria-hidden="true">
              <span className="mt-1 size-2 shrink-0 rounded-full border border-foreground/50 bg-background" />
              <span className="mt-1 w-px flex-1 bg-border" />
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <p className="flex flex-wrap items-baseline gap-x-2 text-xs">
                <span className="font-medium">{t("thread.round", { index: index + 1 })}</span>
                <time dateTime={round.at} className="text-muted-foreground tabular-nums">
                  {say.date(round.at)}
                </time>
                {round.sessionId && round.meetingTitle ? (
                  <Link
                    href={meetingPath(round.sessionId)}
                    dir="auto"
                    className="truncate text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                  >
                    {round.meetingTitle}
                  </Link>
                ) : null}
                {round.from === round.to ? null : (
                  <span className="text-muted-foreground">· {hubWords(`stage.${round.to}`)}</span>
                )}
              </p>
              {round.blocker ? (
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground text-xs">{t("thread.blocker")}</span>
                  <SaidQuote evidence={round.blocker} />
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
