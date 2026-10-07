import Link from "next/link";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Progress } from "@/components/ui/progress";

import type { WorkspaceState } from "../../domain/contract";
import { seatUsage } from "../../domain/people";

/** Seats paid for and taken, with pending invitations counted, so nobody is surprised at the limit. */
export function SeatMeter({ state, canBuy }: { state: WorkspaceState; canBuy: boolean }) {
  const { total, members, pending, left } = seatUsage(state);
  const taken = members + pending;
  const full = left === 0;
  const t = useTranslations("workspaceMembers");
  let note = t("seats.left", { count: left });
  if (full) note = t(canBuy ? "seats.fullAdd" : "seats.fullAsk");
  return (
    <section aria-label={t("seats.label")} className="flex flex-col gap-2.5 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
        <span className="font-medium tabular-nums">
          {t("seats.taken", { taken, total })}{" "}
          <span className="font-normal text-muted-foreground">
            {pending > 0 ? t("seats.breakdownPending", { members, pending }) : t("seats.breakdown", { members })}
          </span>
        </span>
        {canBuy ? (
          <Link
            href="/app/upgrade"
            className="text-muted-foreground text-sm underline-offset-4 hover:text-foreground hover:underline"
          >
            {t("seats.change")}
          </Link>
        ) : null}
      </div>
      <Progress
        value={total === 0 ? 0 : (taken / total) * 100}
        aria-label={t("seats.taken", { taken, total })}
        className={cn(full && "*:data-[slot=progress-indicator]:bg-amber-500")}
      />
      <p className={cn("text-xs", full ? "text-foreground" : "text-muted-foreground")}>{note}</p>
    </section>
  );
}
