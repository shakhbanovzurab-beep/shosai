import { type CatalogPlan, listPublicPlans } from "@/features/admin-plans/server";
import { accountSeat } from "@/features/workspace/server";

import type { Plan, PlanId, PlansResponse, SalesInquiryRequest } from "../domain/contract";

/*
 * In-memory stand-in for the billing backend, used when BACKEND_API_URL is unset. Plans come from
 * Admin › Plans (its demo store), so a plan edited there shows up here at once.
 */

const toPlan = (plan: CatalogPlan): Plan => ({
  id: plan.slug,
  name: plan.name,
  tagline: plan.description,
  audience: plan.audience,
  seats: plan.seats,
  price: plan.custom_pricing ? null : { amount_cents: plan.price_monthly.USD, currency: "USD", interval: "month" },
  entitlements: { ...plan.limits, ...plan.capabilities },
  features: plan.features,
  highlighted: plan.is_featured,
});

/** Plans on sale, cheapest first. */
export const planCatalog = (): Plan[] => listPublicPlans().map(toPlan);

const DEMO_PLAN: PlanId = "basic";
const DEMO_USED_MINUTES = 87;

const nextMonthStart = () => {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)).toISOString();
};

/** The demo user's plan: Basic, or the first plan on sale if Basic was removed in the admin. */
export function demoCurrentPlan(plans = planCatalog()): Plan | undefined {
  return plans.find((p) => p.id === DEMO_PLAN) ?? plans[0];
}

export function demoPlans(): PlansResponse {
  const plans = planCatalog();
  const current = demoCurrentPlan(plans);
  const held = accountSeat();
  const seatPlan = held ? plans.find((p) => p.id === held.plan) : undefined;
  const effective = seatPlan ?? current;
  return {
    plans,
    current_plan_id: current?.id ?? DEMO_PLAN,
    seat: held && seatPlan ? { workspace_name: held.workspace_name, plan_id: seatPlan.id } : null,
    effective_plan_id: effective?.id ?? DEMO_PLAN,
    usage: {
      used_minutes: DEMO_USED_MINUTES,
      limit_minutes: effective?.entitlements.meeting_minutes_per_month ?? null,
      resets_at: nextMonthStart(),
    },
  };
}

/** The limits that apply in Personal right now: the seat's plan when there is one, otherwise the account's. */
export function effectiveEntitlements() {
  const response = demoPlans();
  return response.plans.find((p) => p.id === response.effective_plan_id)?.entitlements ?? null;
}

const shared = globalThis as typeof globalThis & { salesInquiries?: SalesInquiryRequest[] };
const inquiries = shared.salesInquiries ?? [];
shared.salesInquiries = inquiries;

/** Keeps the inquiry so the demo behaves like the real form; nobody is notified. */
export function saveSalesInquiry(inquiry: SalesInquiryRequest) {
  inquiries.push(inquiry);
}
