import type { ReactNode } from "react";

import { CircleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Progress } from "@/components/ui/progress";

import type { MeetingUsage as Usage } from "../domain/contract";
import { usePlanFormat } from "./use-plan-format";

type MeetingUsageProps = {
  usage: Usage;
  /** The paid plan with unlimited meetings, offered once the minutes run out. */
  unlimitedPlan?: string;
  action?: ReactNode;
};

/** Basic's monthly meeting allowance: how much is left, and that meetings pause once it runs out. */
export function MeetingUsage({ usage, unlimitedPlan, action }: MeetingUsageProps) {
  const t = useTranslations("upgrade");
  const { resetDay } = usePlanFormat();
  if (usage.limit_minutes === null) return null;
  const limit = usage.limit_minutes;
  const used = Math.min(usage.used_minutes, limit);
  const left = limit - used;
  const exhausted = left === 0;
  const date = resetDay(usage.resets_at);

  return (
    <section
      aria-label={t("usage.label")}
      className="mx-auto flex w-full max-w-2xl flex-col gap-3 rounded-xl border bg-card p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{exhausted ? t("usage.allUsed") : t("usage.left", { left, limit })}</span>
        <span className="flex items-center gap-3 text-muted-foreground">
          {t("usage.resets", { date })}
          {exhausted ? null : action}
        </span>
      </div>
      <Progress
        value={(used / limit) * 100}
        aria-label={t("usage.used", { used, limit })}
        className={exhausted ? "*:data-[slot=progress-indicator]:bg-destructive" : undefined}
      />
      {exhausted ? (
        <p className="flex items-center gap-2 text-destructive text-sm">
          <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
          {unlimitedPlan ? t("usage.pausedUpgrade", { date, plan: unlimitedPlan }) : t("usage.paused", { date })}
        </p>
      ) : null}
    </section>
  );
}
