import type { PromoCode } from "../domain/contract";
import { prices, SEEDED_AT } from "./demo-seed";

/*
 * Starting promo codes for the in-memory demo, covering every scope (all plans, one plan, several
 * plans, an archived plan), discount kind and status.
 */

export type StoredPromo = Omit<PromoCode, "status">;

const BASE = {
  created_at: SEEDED_AT,
  per_user_limit: 1,
  first_payment_only: false,
  is_active: true,
  percent_off: null,
  amounts_off: {},
  valid_from: null,
  valid_until: null,
  max_redemptions: null,
} satisfies Partial<StoredPromo>;

export const seedPromos = (): StoredPromo[] => [
  {
    ...BASE,
    id: "promo_welcome",
    code: "WELCOME20",
    discount_type: "percent",
    percent_off: 20,
    scope: "all",
    plan_ids: [],
    billing_period: "both",
    max_redemptions: 1000,
    redemptions: 342,
    valid_from: "2026-01-01",
    valid_until: "2026-12-31",
    first_payment_only: true,
  },
  {
    ...BASE,
    id: "promo_pro_year",
    code: "PROYEAR",
    discount_type: "fixed",
    amounts_off: prices(2_000, 25, 22),
    scope: "plans",
    plan_ids: ["plan_professional"],
    billing_period: "year",
    max_redemptions: 500,
    redemptions: 500,
    valid_from: "2026-03-01",
  },
  {
    ...BASE,
    id: "promo_team_start",
    code: "TEAMSTART",
    discount_type: "fixed",
    amounts_off: { RUB: 50_000 },
    scope: "plans",
    plan_ids: ["plan_team"],
    billing_period: "month",
    redemptions: 57,
    first_payment_only: true,
  },
  {
    ...BASE,
    id: "promo_student",
    code: "STUDENT50",
    discount_type: "percent",
    percent_off: 50,
    scope: "plans",
    plan_ids: ["plan_professional"],
    billing_period: "both",
    max_redemptions: 2000,
    redemptions: 811,
    valid_from: "2026-02-01",
    valid_until: "2026-09-01",
  },
  {
    ...BASE,
    id: "promo_black_friday",
    code: "BLACKFRIDAY",
    discount_type: "percent",
    percent_off: 40,
    scope: "all",
    plan_ids: [],
    billing_period: "year",
    max_redemptions: 5000,
    redemptions: 0,
    valid_from: "2026-11-27",
    valid_until: "2026-11-30",
  },
  {
    ...BASE,
    id: "promo_legacy",
    code: "LEGACY10",
    discount_type: "percent",
    percent_off: 10,
    scope: "plans",
    plan_ids: ["plan_pro_2025"],
    billing_period: "both",
    per_user_limit: null,
    redemptions: 12,
    is_active: false,
  },
];
