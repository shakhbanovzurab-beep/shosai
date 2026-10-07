/**
 * Upgrade API contract, shared by the Upgrade page and its route handlers in `../server` (served at
 * `/api/billing/*`). They forward to `${BACKEND_API_URL}/v1/billing/*` when it is set and otherwise
 * answer from an in-memory demo. snake_case to match Pydantic; errors are `{ "detail": string }`.
 * See docs/upgrade-api.md.
 *
 * GET  /billing/plans          → PlansResponse
 * POST /billing/checkout       → CheckoutResponse   (CheckoutRequest; the provider's page for the change)
 * POST /billing/sales-inquiry  → 202 SalesInquiryResponse (SalesInquiryRequest)
 */

/** A plan's slug, e.g. "basic", "professional", "enterprise"; plans are managed in Admin › Plans. */
export type PlanId = string;

/**
 * What a plan unlocks. For a limit, `null` is unlimited and `0` means the feature isn't included.
 * Once a plan's meeting minutes are used, meetings stop for the rest of the month. On a plan with a
 * custom price (`price: null`) storage limits are the starting point, shown as "from 250 GB".
 */
export type Entitlements = {
  meeting_minutes_per_month: number | null;
  file_manager_gb: number | null;
  knowledge_base_mb: number | null;
  shared_workspace: boolean;
  member_management: boolean;
  centralized_billing: boolean;
  sso: boolean;
  admin_controls: boolean;
  priority_support: boolean;
  usage_analytics: boolean;
};

/** The pricing page's tabs. */
export const PLAN_AUDIENCES = ["individual", "team", "enterprise"] as const;
export type PlanAudience = (typeof PLAN_AUDIENCES)[number];

export type Plan = {
  id: PlanId;
  name: string;
  tagline: string;
  audience: PlanAudience;
  /** For team plans: how many users it can be bought for; the price is then per user. */
  seats: { min: number; max: number | null } | null;
  /** Per month (per user when `seats` is set), in minor units; null for a custom, sales-negotiated price. */
  price: { amount_cents: number; currency: string; interval: "month" } | null;
  entitlements: Entitlements;
  /** Extra card lines shown before the limits, e.g. "Everything in Basic". */
  features: string[];
  /** Shown as the recommended choice. */
  highlighted: boolean;
};

/** Meeting minutes this calendar month; `limit` is null on unlimited plans. */
export type MeetingUsage = { used_minutes: number; limit_minutes: number | null; resets_at: string };

export type PlansResponse = {
  /** Ascending, cheapest first. */
  plans: Plan[];
  /** The account's own plan. */
  current_plan_id: PlanId;
  /** A seat in a team workspace whose plan also covers the member's own tools; null without one. */
  seat: { workspace_name: string; plan_id: PlanId } | null;
  /** The plan whose limits apply in Personal: the seat's when there is one, otherwise the account's. */
  effective_plan_id: PlanId;
  /** Against the effective plan. */
  usage: MeetingUsage;
};

/** Any plan with a price; custom-priced plans go through sales. Returns the payment provider's page. */
export type CheckoutRequest = {
  plan_id: PlanId /** Required for a plan with `seats`, within its range. */;
  seats?: number;
};
export type CheckoutResponse = { url: string };

export const TEAM_SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"] as const;
export type TeamSize = (typeof TEAM_SIZES)[number];

export type SalesInquiryRequest = {
  work_email: string;
  company: string;
  team_size: TeamSize;
  message: string;
};
export type SalesInquiryResponse = { status: "received" };

export const COMPANY_MAX = 120;
export const MESSAGE_MAX = 2000;
