"use client";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { PLAN_AUDIENCES, type Plan, type PlanId } from "../domain/contract";
import { PlanCard } from "./plan-card";

/** The users the team plans cover together, e.g. 2–100; `max: null` is open-ended. */
function seatRange(plans: Plan[]) {
  const ranges = plans.flatMap((p) => (p.seats ? [p.seats] : []));
  if (ranges.length === 0) return null;
  const min = Math.min(...ranges.map((r) => r.min));
  const max = ranges.some((r) => r.max === null) ? null : Math.max(...ranges.map((r) => r.max ?? 0));
  return { min, max };
}

/** Fewer cards get a narrower, centred grid instead of stretching across the page. */
const GRID: Record<number, string> = { 1: "mx-auto w-full max-w-md", 2: "mx-auto w-full max-w-4xl md:grid-cols-2" };

/** Individual, Team and Enterprise plans on separate tabs; the tab of the current plan opens first. */
export function PlanTabs({ plans, currentPlanId }: { plans: Plan[]; currentPlanId: PlanId }) {
  const t = useTranslations("upgrade");
  const groups = PLAN_AUDIENCES.map((audience) => ({
    audience,
    plans: plans.filter((p) => p.audience === audience),
  })).filter((group) => group.plans.length > 0);
  const current = plans.find((p) => p.id === currentPlanId)?.audience;

  return (
    <Tabs defaultValue={current ?? groups[0]?.audience} className="gap-6">
      <TabsList className="mx-auto">
        {groups.map(({ audience, plans: inTab }) => {
          const range = audience === "team" ? seatRange(inTab) : null;
          return (
            <TabsTrigger key={audience} value={audience} className="px-4">
              {t(`audiences.${audience}`)}
              {range ? (
                <span className="font-normal text-muted-foreground">
                  {range.max === null
                    ? t("seatRangeOpen", { min: range.min })
                    : t("seatRange", { min: range.min, max: range.max })}
                </span>
              ) : null}
            </TabsTrigger>
          );
        })}
      </TabsList>
      {groups.map(({ audience, plans: inTab }) => (
        <TabsContent key={audience} value={audience}>
          <div className={cn("grid items-start gap-4", GRID[inTab.length] ?? "lg:grid-cols-3")}>
            {inTab.map((plan) => (
              <PlanCard key={plan.id} plan={plan} plans={plans} currentPlanId={currentPlanId} />
            ))}
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
