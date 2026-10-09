import type { Plan, PlanCapabilities, Prices } from "../domain/contract";

/*
 * Starting plans for the in-memory demo in `demo-store.ts` (used when no backend is configured): the
 * four public plans and one archived legacy plan. Promo codes are in `demo-seed-promos.ts`.
 */

export const SEEDED_AT = "2026-01-15T09:00:00.000Z";

/** Major units → minor units per currency. */
export const prices = (rub: number, usd: number, eur: number): Prices => ({
  RUB: rub * 100,
  USD: usd * 100,
  EUR: eur * 100,
});
const FREE = prices(0, 0, 0);

const NO_CAPABILITIES: PlanCapabilities = {
  shared_workspace: false,
  member_management: false,
  centralized_billing: false,
  sso: false,
  admin_controls: false,
  priority_support: false,
  usage_analytics: false,
};

type Defaults =
  | "created_at"
  | "updated_at"
  | "is_featured"
  | "archived"
  | "is_active"
  | "custom_pricing"
  | "capabilities"
  | "audience"
  | "seats";
type SeedPlan = Omit<Plan, Defaults> & Partial<Pick<Plan, Defaults>>;

const plan = ({
  is_featured = false,
  archived = false,
  is_active = true,
  custom_pricing = false,
  capabilities = NO_CAPABILITIES,
  audience = "individual",
  seats = null,
  ...rest
}: SeedPlan): Plan => ({
  ...rest,
  is_featured,
  archived,
  is_active,
  custom_pricing,
  capabilities,
  audience,
  seats,
  created_at: SEEDED_AT,
  updated_at: SEEDED_AT,
});

/* Plan names, descriptions and card lines are what customers see on the Upgrade page, so they are in English. */
export const seedPlans = (): Plan[] => [
  plan({
    id: "plan_basic",
    name: "Basic",
    slug: "basic",
    description: "Try Shosai on your own meetings.",
    price_monthly: FREE,
    price_yearly: FREE,
    limits: { meeting_minutes_per_month: 120, file_manager_gb: 0, knowledge_base_mb: 0 },
    features: ["Leo, Mail, Calendar, Kanban and Notes"],
    sort_order: 0,
    subscribers: 12_840,
  }),
  plan({
    id: "plan_professional",
    name: "Professional",
    slug: "professional",
    description: "Everything, without limits on meetings.",
    price_monthly: prices(1_490, 15, 14),
    price_yearly: prices(17_880, 180, 168),
    limits: { meeting_minutes_per_month: null, file_manager_gb: 100, knowledge_base_mb: 100 },
    features: ["Everything in Basic"],
    is_featured: true,
    sort_order: 10,
    subscribers: 3_412,
  }),
  plan({
    id: "plan_team",
    name: "Team",
    slug: "team",
    description: "Professional for every member, in one shared workspace.",
    audience: "team",
    seats: { min: 2, max: 100 },
    price_monthly: prices(1_990, 20, 18),
    price_yearly: prices(23_880, 240, 216),
    limits: { meeting_minutes_per_month: null, file_manager_gb: 100, knowledge_base_mb: 100 },
    capabilities: { ...NO_CAPABILITIES, shared_workspace: true, member_management: true, centralized_billing: true },
    features: ["Everything in Professional, for each member"],
    sort_order: 20,
    subscribers: 418,
  }),
  plan({
    id: "plan_enterprise",
    name: "Enterprise",
    slug: "enterprise",
    description: "Enterprise-grade security and admin controls.",
    custom_pricing: true,
    price_monthly: FREE,
    price_yearly: FREE,
    limits: { meeting_minutes_per_month: null, file_manager_gb: 250, knowledge_base_mb: 1_024 },
    audience: "enterprise",
    capabilities: {
      shared_workspace: true,
      member_management: true,
      centralized_billing: true,
      sso: true,
      admin_controls: true,
      priority_support: true,
      usage_analytics: true,
    },
    features: ["Everything in Team"],
    sort_order: 30,
    subscribers: 27,
  }),
  plan({
    id: "plan_pro_2025",
    name: "Pro (2025)",
    slug: "pro-2025",
    description: "The previous Pro plan, kept for its current subscribers.",
    price_monthly: prices(790, 9, 9),
    price_yearly: prices(7_900, 90, 90),
    limits: { meeting_minutes_per_month: 600, file_manager_gb: 20, knowledge_base_mb: 50 },
    features: [],
    is_active: false,
    archived: true,
    sort_order: 90,
    subscribers: 96,
  }),
];
