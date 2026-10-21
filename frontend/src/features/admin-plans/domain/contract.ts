/**
 * Admin › Plans and promo codes API contract, shared by the slice's UI and its route handlers in
 * `src/features/admin-plans/server` (served at `/api/admin/plans` and `/api/admin/promo-codes`). They
 * proxy to `${BACKEND_API_URL}/v1/admin/plans` and `/v1/admin/promo-codes` when it is set and fall back
 * to an in-memory demo otherwise. snake_case to match Pydantic; errors are FastAPI's `{ "detail": string }`.
 * Money is in minor units (kopecks, cents) per currency; dates are calendar days, `YYYY-MM-DD`, inclusive.
 */

/* ---------- Currencies ---------- */

/** Plans are sold in these currencies; every plan has a price in each. */
export const CURRENCIES = ["RUB", "USD", "EUR"] as const;
export type Currency = (typeof CURRENCIES)[number];
/** An amount in minor units per currency, e.g. `{ RUB: 99000, USD: 1200, EUR: 1100 }`. */
export type Prices = Record<Currency, number>;
export const CURRENCY_SYMBOL: Record<Currency, string> = { RUB: "₽", USD: "$", EUR: "€" };
export const CURRENCY_NAME: Record<Currency, string> = { RUB: "Рубли", USD: "Доллары", EUR: "Евро" };

/* ---------- Plans: GET/POST /admin/plans, PATCH/DELETE /admin/plans/{id} ---------- */

/**
 * What a plan includes. For a limit, `null` means "no limit" and `0` means the feature isn't included.
 * Once a plan's meeting minutes are used up, meetings stop until the next calendar month.
 */
export type PlanLimits = {
  meeting_minutes_per_month: number | null;
  /** File Manager storage, in GB. */
  file_manager_gb: number | null;
  /** Knowledge base storage, in MB (1024 MB is shown as 1 GB). */
  knowledge_base_mb: number | null;
};

/** Which tab of the pricing page the plan is on. */
export const PLAN_AUDIENCES = ["individual", "team", "enterprise"] as const;
export type PlanAudience = (typeof PLAN_AUDIENCES)[number];
export const PLAN_AUDIENCE_LABEL: Record<PlanAudience, string> = {
  individual: "Для себя",
  team: "Для команды",
  enterprise: "Enterprise",
};

/** How many users a plan is for. When set, the price is per user per period. */
export type PlanSeats = { min: number; max: number | null };

/** Team and enterprise extras a plan may switch on. */
export const PLAN_CAPABILITIES = [
  "shared_workspace",
  "member_management",
  "centralized_billing",
  "sso",
  "admin_controls",
  "priority_support",
  "usage_analytics",
] as const;
export type PlanCapability = (typeof PLAN_CAPABILITIES)[number];
export type PlanCapabilities = Record<PlanCapability, boolean>;
export const PLAN_CAPABILITY_LABEL: Record<PlanCapability, string> = {
  shared_workspace: "Общее рабочее пространство",
  member_management: "Управление участниками",
  centralized_billing: "Единый счёт",
  sso: "Единый вход (SSO)",
  admin_controls: "Безопасность и административный контроль",
  priority_support: "Приоритетная поддержка",
  usage_analytics: "Аналитика использования",
};

export type Plan = {
  id: string;
  name: string;
  /** Unique, `a-z0-9-`; used in checkout links and by the desktop apps. */
  slug: string;
  description: string;
  audience: PlanAudience;
  /** null for a single-user plan. */
  seats: PlanSeats | null;
  /**
   * The price is agreed with sales: the pricing page shows "Custom" and a sales form instead of
   * checkout, and both price fields are zero.
   */
  custom_pricing: boolean;
  /** Per month when billed monthly, in every currency; all zero for a free plan. */
  price_monthly: Prices;
  /** Per year when billed yearly, in every currency. */
  price_yearly: Prices;
  limits: PlanLimits;
  capabilities: PlanCapabilities;
  /** Extra lines for the pricing card, shown before the limits ("Everything in Basic"). */
  features: string[];
  /** Offered to new customers. */
  is_active: boolean;
  /** Highlighted on the pricing page. */
  is_featured: boolean;
  /** Ascending order on the pricing page. */
  sort_order: number;
  /** Current paying or free subscribers; read-only. */
  subscribers: number;
  /** Archived plans keep their subscribers but can't be bought or edited until restored. */
  archived: boolean;
  created_at: string;
  updated_at: string;
};

export type PlanDraft = Omit<Plan, "id" | "subscribers" | "archived" | "created_at" | "updated_at">;
/** Any subset of the draft; `archived: false` restores an archived plan. */
export type PlanPatch = Partial<PlanDraft> & { archived?: boolean };

export type PlansResponse = { plans: Plan[] };

/**
 * DELETE removes a plan without subscribers and archives one with subscribers. A removed plan is
 * also removed from every promo code's scope; a promo code left without plans is switched off.
 */
export type PlanDeleteResponse =
  | { result: "deleted"; plan: null; promo_codes_updated: number }
  | { result: "archived"; plan: Plan; promo_codes_updated: 0 };

/* ---------- Promo codes: GET/POST /admin/promo-codes, PATCH/DELETE /admin/promo-codes/{id} ---------- */

export const DISCOUNT_TYPES = ["percent", "fixed"] as const;
export type DiscountType = (typeof DISCOUNT_TYPES)[number];

export const BILLING_PERIODS = ["month", "year", "both"] as const;
export type BillingPeriodScope = (typeof BILLING_PERIODS)[number];

export const PROMO_SCOPES = ["all", "plans"] as const;
export type PromoScope = (typeof PROMO_SCOPES)[number];

/** Derived by the server from the fields below and today's date. */
export type PromoStatus = "active" | "scheduled" | "expired" | "exhausted" | "disabled";

export type PromoCode = {
  id: string;
  /** Unique, upper-case `A-Z0-9_-`, 3–32 characters. */
  code: string;
  /** "percent" works in any currency; "fixed" only in the currencies listed in `amounts_off`. */
  discount_type: DiscountType;
  /** 1–100 when the type is "percent", otherwise null. */
  percent_off: number | null;
  /**
   * Minor units off per currency when the type is "fixed" (at least one currency); empty for "percent".
   * A payment in a currency missing here doesn't accept the code.
   */
  amounts_off: Partial<Prices>;
  /** "all" applies to every plan, including ones added later; "plans" only to `plan_ids`. */
  scope: PromoScope;
  /** Empty when scope is "all". */
  plan_ids: string[];
  billing_period: BillingPeriodScope;
  /** Total redemptions allowed; null is unlimited. */
  max_redemptions: number | null;
  /** Redemptions allowed per user; null is unlimited. */
  per_user_limit: number | null;
  /** Read-only. */
  redemptions: number;
  valid_from: string | null;
  valid_until: string | null;
  first_payment_only: boolean;
  is_active: boolean;
  status: PromoStatus;
  created_at: string;
};

export type PromoCodeDraft = Omit<PromoCode, "id" | "redemptions" | "status" | "created_at">;
export type PromoCodePatch = Partial<PromoCodeDraft>;

export type PromoCodesResponse = { promo_codes: PromoCode[] };

/* ---------- Limits shared by forms and validation ---------- */

export const PLAN_NAME_MAX = 60;
export const PLAN_DESCRIPTION_MAX = 300;
export const PLAN_FEATURES_MAX = 20;
export const PLAN_FEATURE_MAX = 120;
/** 10 000 000 major units (₽, $, €) in minor units. */
export const PRICE_MAX = 1_000_000_000;
export const PROMO_CODE_MIN = 3;
export const PROMO_CODE_MAX = 32;

/** Whether a promo code is in force on `today` (YYYY-MM-DD), given its fields. */
export function promoStatus(
  promo: Pick<PromoCode, "is_active" | "valid_from" | "valid_until" | "max_redemptions" | "redemptions">,
  today: string,
): PromoStatus {
  if (!promo.is_active) return "disabled";
  if (promo.valid_until !== null && promo.valid_until < today) return "expired";
  if (promo.max_redemptions !== null && promo.redemptions >= promo.max_redemptions) return "exhausted";
  if (promo.valid_from !== null && promo.valid_from > today) return "scheduled";
  return "active";
}
