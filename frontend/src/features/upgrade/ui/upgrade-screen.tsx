"use client";

import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { plansResource, usePlans } from "../model/plans-resource";
import { MeetingUsage } from "./meeting-usage";
import { PlanComparison } from "./plan-comparison";
import { PlanTabs } from "./plan-tabs";

/** The free plan's monthly meeting minutes, as the header promises them. */
const FREE_MEETING_MINUTES = 120;

function Loading() {
  const t = useTranslations("upgrade");
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-112 rounded-xl" />
      <Skeleton className="h-112 rounded-xl" />
      <Skeleton className="h-112 rounded-xl" />
    </div>
  );
}

/** The plans on sale in Individual, Team and Enterprise tabs, the current plan marked, then a full comparison. */
export function UpgradeScreen() {
  const t = useTranslations("upgrade");
  const state = usePlans();

  let body: ReactNode;
  if (state.status === "loading") body = <Loading />;
  else if (state.status === "error")
    body = <LoadError title={t("loadFailed")} message={state.message} onRetry={() => void plansResource.refresh()} />;
  else {
    const { plans, current_plan_id, usage, seat } = state.data;
    const seatPlan = seat ? plans.find((p) => p.id === seat.plan_id) : undefined;
    const unlimited = plans.find((p) => p.entitlements.meeting_minutes_per_month === null && p.price !== null);
    body = (
      <>
        {seat && seatPlan ? (
          <p className="mx-auto max-w-2xl rounded-xl border bg-muted/40 px-4 py-3 text-center text-sm">
            {t.rich("seatNote", {
              workspace: seat.workspace_name,
              plan: seatPlan.name,
              b: (chunks) => <bdi className="font-medium">{chunks}</bdi>,
            })}
          </p>
        ) : null}
        <MeetingUsage usage={usage} unlimitedPlan={unlimited?.name} />
        <PlanTabs plans={plans} currentPlanId={current_plan_id} />
        <PlanComparison plans={plans} />
        <p className="text-center text-muted-foreground text-xs">{t("pricesNote")}</p>
      </>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
      <header className="flex flex-col items-center gap-2 pt-2 text-center">
        <h1 className="font-semibold text-2xl tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="text-balance text-muted-foreground">{t("subtitle", { minutes: FREE_MEETING_MINUTES })}</p>
      </header>
      {body}
    </div>
  );
}
