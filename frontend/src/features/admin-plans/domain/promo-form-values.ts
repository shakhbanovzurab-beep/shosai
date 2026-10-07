import {
  type BillingPeriodScope,
  CURRENCIES,
  type Currency,
  type DiscountType,
  PROMO_CODE_MAX,
  type PromoCode,
  type PromoScope,
} from "./contract";
import { moneyInput, optionalIntInput, parseInt10, parseMoney, parseOptionalInt } from "./format";
import { randomCode } from "./promo-code";

/* The promo code form's text state and its conversion to and from the API's PromoCodeDraft. */

export type PromoValues = {
  code: string;
  discount_type: DiscountType;
  percent_off: string;
  /** Currencies a fixed discount applies to; the code is refused for payments in the others. */
  currencies: Currency[];
  amounts: Record<Currency, string>;
  scope: PromoScope;
  plan_ids: string[];
  billing_period: BillingPeriodScope;
  max_redemptions: string;
  per_user_limit: string;
  valid_from: string;
  valid_until: string;
  first_payment_only: boolean;
  is_active: boolean;
};

export type PromoTextKey = { [K in keyof PromoValues]: PromoValues[K] extends string ? K : never }[keyof PromoValues];

/** What the form opens with: a blank code, an existing one, or a copy of one. */
export type PromoFormTarget =
  | { mode: "create" }
  | { mode: "edit"; promo: PromoCode }
  | { mode: "copy"; promo: PromoCode };

function valuesOf(promo: PromoCode): PromoValues {
  const amounts = { RUB: "", USD: "", EUR: "" };
  for (const currency of CURRENCIES) {
    const amount = promo.amounts_off[currency];
    if (amount !== undefined) amounts[currency] = moneyInput(amount);
  }
  return {
    code: promo.code,
    discount_type: promo.discount_type,
    percent_off: promo.percent_off === null ? "10" : String(promo.percent_off),
    currencies: CURRENCIES.filter((currency) => promo.amounts_off[currency] !== undefined),
    amounts,
    scope: promo.scope,
    plan_ids: promo.plan_ids,
    billing_period: promo.billing_period,
    max_redemptions: optionalIntInput(promo.max_redemptions),
    per_user_limit: optionalIntInput(promo.per_user_limit),
    valid_from: promo.valid_from ?? "",
    valid_until: promo.valid_until ?? "",
    first_payment_only: promo.first_payment_only,
    is_active: promo.is_active,
  };
}

export function initialPromoValues(target: PromoFormTarget): PromoValues {
  if (target.mode === "edit") return valuesOf(target.promo);
  if (target.mode === "copy")
    return { ...valuesOf(target.promo), code: `${target.promo.code.slice(0, PROMO_CODE_MAX - 5)}-${randomCode(4)}` };
  return {
    code: randomCode(8),
    discount_type: "percent",
    percent_off: "10",
    currencies: [...CURRENCIES],
    amounts: { RUB: "", USD: "", EUR: "" },
    scope: "all",
    plan_ids: [],
    billing_period: "both",
    max_redemptions: "",
    per_user_limit: "1",
    valid_from: "",
    valid_until: "",
    first_payment_only: false,
    is_active: true,
  };
}

/** The draft to validate; only the chosen currencies carry an amount. */
export function promoCandidateOf(values: PromoValues) {
  const fixed = values.discount_type === "fixed";
  const chosen = new Set(values.currencies);
  return {
    code: values.code,
    discount_type: values.discount_type,
    percent_off: fixed ? null : parseInt10(values.percent_off),
    amounts_off: Object.fromEntries(
      CURRENCIES.filter((c) => fixed && chosen.has(c)).map((c) => [c, parseMoney(values.amounts[c])]),
    ),
    scope: values.scope,
    plan_ids: values.plan_ids,
    billing_period: values.billing_period,
    max_redemptions: parseOptionalInt(values.max_redemptions),
    per_user_limit: parseOptionalInt(values.per_user_limit),
    valid_from: values.valid_from || null,
    valid_until: values.valid_until || null,
    first_payment_only: values.first_payment_only,
    is_active: values.is_active,
  };
}

export const promoInputId = (key: string) => `promo-${key.replaceAll("_", "-").replaceAll(".", "-")}`;
/** `plan_ids.0` → `plan_ids`; `amounts_off.USD` stays, matching the amount input. */
export const promoFieldKey = (path: string) => (path.startsWith("plan_ids") ? "plan_ids" : path);
