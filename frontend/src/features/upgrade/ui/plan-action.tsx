"use client";

import { useTransition } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import type { Plan, PlanId } from "../domain/contract";
import { isUpgrade } from "../domain/plan-features";
import { startCheckout } from "../model/plan-actions";
import { SalesDialog } from "./sales-dialog";

/**
 * The card's button: nothing to do on the current plan, sales for a custom-priced plan, otherwise the payment
 * provider's page for the change. Card details are only ever entered there.
 */
type PlanActionProps = {
  plan: Plan;
  plans: Plan[];
  currentPlanId: PlanId /** Users, for a per-user plan. */;
  seats?: number;
};

export function PlanAction({ plan, plans, currentPlanId, seats }: PlanActionProps) {
  const t = useTranslations("upgrade");
  const [pending, startTransition] = useTransition();

  if (plan.id === currentPlanId) {
    return (
      <Button variant="outline" className="w-full" disabled>
        {t("action.current")}
      </Button>
    );
  }
  if (plan.price === null) return <SalesDialog />;

  const planId = plan.id;
  const upgrade = isUpgrade(plans, currentPlanId, planId);
  const checkout = () =>
    startTransition(() =>
      startCheckout({ plan_id: planId, seats }, upgrade ? t("action.upgradeFailed") : t("action.switchFailed")),
    );

  return (
    <Button variant={upgrade ? "default" : "outline"} className="w-full" disabled={pending} onClick={checkout}>
      {pending ? <Spinner data-icon="inline-start" /> : null}
      {upgrade ? t("action.upgradeTo", { plan: plan.name }) : t("action.switchTo", { plan: plan.name })}
    </Button>
  );
}
