"use client";

import type { ReactNode } from "react";

import { BookLock, FolderLock } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import type { Plan } from "../domain/contract";
import { usePlans } from "../model/plans-resource";
import { usePlanFormat } from "./use-plan-format";

export type GatedFeature = "file_manager" | "knowledge_base";

const FEATURES = {
  file_manager: {
    icon: FolderLock,
    /** The plan's storage in bytes, or null when unlimited. */
    bytes: (plan: Plan) => {
      const gb = plan.entitlements.file_manager_gb;
      return gb === null ? null : gb * 1024 ** 3;
    },
    limit: (plan: Plan) => plan.entitlements.file_manager_gb,
  },
  knowledge_base: {
    icon: BookLock,
    bytes: (plan: Plan) => {
      const mb = plan.entitlements.knowledge_base_mb;
      return mb === null ? null : mb * 1024 ** 2;
    },
    limit: (plan: Plan) => plan.entitlements.knowledge_base_mb,
  },
} satisfies Record<GatedFeature, unknown>;

export function GateLoading() {
  const t = useTranslations("upgrade");
  return (
    <div className="flex min-h-64 items-center justify-center">
      <Spinner className="size-6 text-muted-foreground" />
      <span className="sr-only">{t("gate.checking")}</span>
    </div>
  );
}

/** Explains what the feature is and which plan includes it, with the way to upgrade. */
function LockedFeature({ feature, plan }: { feature: GatedFeature; plan: Plan | undefined }) {
  const t = useTranslations("upgrade");
  const locale = useLocale();
  const { price } = usePlanFormat();
  const { icon: Icon, bytes } = FEATURES[feature];
  let offer: string | null = null;
  if (plan) {
    const amount = bytes(plan);
    const values = {
      plan: plan.name,
      unlimited: amount === null ? "yes" : "no",
      amount: formatBytes(locale, amount ?? 0),
    };
    offer = plan.price
      ? t("gate.offerPriced", { ...values, price: price(plan.price.amount_cents, plan.price.currency) })
      : t("gate.offer", values);
  }
  return (
    <Empty className="min-h-[60vh]">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>
          {plan ? t(`gate.${feature}.partOf`, { plan: plan.name }) : t(`gate.${feature}.notInPlan`)}
        </EmptyTitle>
        <EmptyDescription>{t(`gate.${feature}.pitch`)}</EmptyDescription>
        {offer ? <EmptyDescription>{offer}</EmptyDescription> : null}
      </EmptyHeader>
      <EmptyContent className="flex-row justify-center gap-2">
        <Button asChild>
          <Link href="/app/upgrade">{plan ? t("gate.upgradeTo", { plan: plan.name }) : t("gate.seePlans")}</Link>
        </Button>
        {plan ? (
          <Button asChild variant="outline">
            <Link href="/app/upgrade#compare-plans">{t("gate.comparePlans")}</Link>
          </Button>
        ) : null}
      </EmptyContent>
    </Empty>
  );
}

/**
 * Shows the feature only when the current plan includes it. If the plan can't be loaded the feature
 * is shown anyway: the backend enforces the limits, the gate only explains them.
 */
export function FeatureGate({ feature, children }: { feature: GatedFeature; children: ReactNode }) {
  const state = usePlans();
  if (state.status === "loading") return <GateLoading />;
  if (state.status === "error") return children;

  const { plans, effective_plan_id } = state.data;
  const { limit } = FEATURES[feature];
  // A seat in a team workspace counts: its plan covers the member's own tools too.
  const current = plans.find((p) => p.id === effective_plan_id);
  if (!current || limit(current) !== 0) return children;

  // The cheapest plan that includes it, preferring one that can be bought right away.
  const unlocking = plans.filter((p) => limit(p) !== 0);
  return <LockedFeature feature={feature} plan={unlocking.find((p) => p.price !== null) ?? unlocking[0]} />;
}
