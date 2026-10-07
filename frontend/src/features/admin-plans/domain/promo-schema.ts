import { z } from "zod";

import {
  BILLING_PERIODS,
  CURRENCIES,
  CURRENCY_SYMBOL,
  DISCOUNT_TYPES,
  PROMO_CODE_MAX,
  PROMO_CODE_MIN,
  PROMO_SCOPES,
} from "./contract";
import { money } from "./schema";

const CODE_PATTERN = /^[A-Z0-9_-]+$/;
const isoDate = (message: string) => z.iso.date({ error: message }).nullable();
/** A fixed discount is at least one major unit (1 ₽, $1, €1). */
const amountOff = (symbol: string) => money(`Скидка, ${symbol}`, 100).optional();

export const promoFields = z.object({
  code: z
    .string({ error: "Укажите код." })
    .trim()
    .toUpperCase()
    .min(PROMO_CODE_MIN, `Код — от ${PROMO_CODE_MIN} до ${PROMO_CODE_MAX} символов.`)
    .max(PROMO_CODE_MAX, `Код — от ${PROMO_CODE_MIN} до ${PROMO_CODE_MAX} символов.`)
    .regex(CODE_PATTERN, "Код: только латинские буквы, цифры, дефис и подчёркивание."),
  discount_type: z.enum(DISCOUNT_TYPES, { error: "Выберите тип скидки." }),
  percent_off: z
    .int({ error: "Укажите процент скидки целым числом." })
    .min(1, "Процент скидки — от 1 до 100.")
    .max(100, "Процент скидки — от 1 до 100.")
    .nullable(),
  amounts_off: z.object({
    RUB: amountOff(CURRENCY_SYMBOL.RUB),
    USD: amountOff(CURRENCY_SYMBOL.USD),
    EUR: amountOff(CURRENCY_SYMBOL.EUR),
  }),
  scope: z.enum(PROMO_SCOPES, { error: "Выберите, к каким тарифам применяется код." }),
  plan_ids: z.array(z.string().min(1)).max(50, "Слишком много тарифов."),
  billing_period: z.enum(BILLING_PERIODS, { error: "Выберите период оплаты." }),
  max_redemptions: z
    .int({ error: "Лимит активаций: целое число или пусто." })
    .min(1, "Лимит активаций — не меньше 1.")
    .max(10_000_000, "Лимит активаций слишком большой.")
    .nullable(),
  per_user_limit: z
    .int({ error: "Лимит на пользователя: целое число или пусто." })
    .min(1, "Лимит на пользователя — не меньше 1.")
    .max(1000, "Лимит на пользователя — не больше 1000.")
    .nullable(),
  valid_from: isoDate("Неверная дата начала."),
  valid_until: isoDate("Неверная дата окончания."),
  first_payment_only: z.boolean(),
  is_active: z.boolean(),
});

type PromoFields = z.infer<typeof promoFields>;

function checkPromo(promo: PromoFields, ctx: z.RefinementCtx) {
  if (promo.discount_type === "percent" && promo.percent_off === null)
    ctx.addIssue({ code: "custom", path: ["percent_off"], message: "Укажите процент скидки." });
  if (promo.discount_type === "fixed" && CURRENCIES.every((c) => promo.amounts_off[c] === undefined))
    ctx.addIssue({
      code: "custom",
      path: ["amounts_off"],
      message: "Выберите хотя бы одну валюту и укажите сумму скидки.",
    });
  if (promo.scope === "plans" && promo.plan_ids.length === 0)
    ctx.addIssue({ code: "custom", path: ["plan_ids"], message: "Выберите хотя бы один тариф." });
  if (promo.valid_from !== null && promo.valid_until !== null && promo.valid_until < promo.valid_from)
    ctx.addIssue({
      code: "custom",
      path: ["valid_until"],
      message: "Дата окончания не может быть раньше даты начала.",
    });
  if (promo.max_redemptions !== null && promo.per_user_limit !== null && promo.per_user_limit > promo.max_redemptions)
    ctx.addIssue({
      code: "custom",
      path: ["per_user_limit"],
      message: "Лимит на пользователя не может быть больше общего лимита.",
    });
}

/**
 * Normalises the draft: a percent code carries no amounts and a fixed one no percent; scope "all"
 * never carries plan ids, and ids are unique.
 */
export const promoDraftSchema = promoFields.superRefine(checkPromo).transform((promo) => ({
  ...promo,
  percent_off: promo.discount_type === "percent" ? promo.percent_off : null,
  amounts_off: promo.discount_type === "fixed" ? promo.amounts_off : {},
  plan_ids: promo.scope === "all" ? [] : [...new Set(promo.plan_ids)],
}));
/** Shape check for PATCH; the merged promo code is then checked again with `promoDraftSchema`. */
export const promoPatchSchema = promoFields.partial();
