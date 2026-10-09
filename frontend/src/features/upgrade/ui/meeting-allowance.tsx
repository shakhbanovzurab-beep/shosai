"use client";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Link } from "@/lib/navigation";

import { usePlans } from "../model/plans-resource";
import { usePlanFormat } from "./use-plan-format";

/**
 * The plan's monthly meeting minutes, for plans that have a limit (Basic). Once they're used,
 * Shosai stops capturing meetings until the reset; the meetings and their notes stay available.
 */
export function MeetingAllowance() {
  const t = useTranslations("upgrade");
  const { resetDay } = usePlanFormat();
  const state = usePlans();
  if (state.status !== "ready") return null;
  const { usage, plans } = state.data;
  if (usage.limit_minutes === null) return null;

  const limit = usage.limit_minutes;
  const used = Math.min(usage.used_minutes, limit);
  const left = limit - used;
  const exhausted = left === 0;
  const date = resetDay(usage.resets_at);
  const unlimited = plans.find((p) => p.entitlements.meeting_minutes_per_month === null && p.price !== null);

  return (
    <section aria-label={t("usage.label")} className="flex flex-col gap-2.5 rounded-xl border bg-card p-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-medium">{t("usage.title")}</span>
        <span className="text-muted-foreground text-xs tabular-nums">{t("usage.ratio", { used, limit })}</span>
      </div>
      <Progress
        value={(used / limit) * 100}
        aria-label={t("usage.used", { used, limit })}
        className={cn(exhausted && "*:data-[slot=progress-indicator]:bg-destructive")}
      />
      <p className={cn("text-xs", exhausted ? "text-destructive" : "text-muted-foreground")}>
        {exhausted ? t("usage.recordingPaused", { date }) : t("usage.leftShort", { left, date })}
      </p>
      {unlimited ? (
        <Button asChild size="sm" variant={exhausted ? "default" : "outline"}>
          <Link href="/app/upgrade">{t("usage.getUnlimited")}</Link>
        </Button>
      ) : null}
    </section>
  );
}
