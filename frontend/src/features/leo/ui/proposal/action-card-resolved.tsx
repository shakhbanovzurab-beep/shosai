"use client";

import { cn } from "cn";
import { CircleAlert, CircleCheck, CircleX } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { outcomeOf } from "../../domain/card-labels";
import type { LeoProposal, ProposalStatus } from "../../domain/proposals";

/* Решённая карточка одной строкой (Leo §13.3): что вышло, когда и, если не вышло, почему — словами по коду. */

const DONE: ReadonlySet<ProposalStatus> = new Set(["succeeded", "partially_succeeded"]);

/** Итог: выполнено — зелёная галочка, неизвестно — вопрос к человеку, остальное — крестик. */
function StatusIcon({ status }: { status: ProposalStatus }) {
  const base = "mt-0.5 size-4 shrink-0";
  if (DONE.has(status)) {
    return <CircleCheck aria-hidden="true" className={cn(base, "text-emerald-600 dark:text-emerald-400")} />;
  }
  if (status === "outcome_unknown")
    return <CircleAlert aria-hidden="true" className={cn(base, "text-muted-foreground")} />;
  return <CircleX aria-hidden="true" className={cn(base, "text-muted-foreground")} />;
}

/** Решённое действие одной строкой: что вышло и когда; `outcome_unknown` прямо просит проверить. */
export function ActionCardResolved({ proposal }: { proposal: LeoProposal }) {
  const t = useTranslations("leoCards");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  const when = proposal.resolved_at ? format.relativeTime(new Date(proposal.resolved_at), now) : null;
  const outcome = outcomeOf(proposal.outcome);
  return (
    <div role="status" className="flex items-start gap-2.5 rounded-xl border bg-card px-3 py-2.5 text-sm">
      <StatusIcon status={proposal.status} />
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium" dir="auto">
          {proposal.title}
        </span>
        <span className="text-muted-foreground text-xs">
          {t(`card.status.${proposal.status}`)}
          {when ? ` · ${when}` : null}
          {outcome ? ` · ${t(`card.outcome.${outcome}`)}` : null}
        </span>
      </div>
    </div>
  );
}
