import { z } from "zod";

import {
  CURRENCIES,
  PLAN_AUDIENCES,
  PLAN_CAPABILITIES,
  PLAN_DESCRIPTION_MAX,
  PLAN_FEATURE_MAX,
  PLAN_FEATURES_MAX,
  PLAN_NAME_MAX,
  type Prices,
} from "./contract";
import { pricesSchema } from "./schema";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const limit = (label: string, max: number) =>
  z
    .int({ error: `${label}: укажите целое число или оставьте поле пустым.` })
    .min(0, `${label}: не меньше 0.`)
    .max(max, `${label}: слишком большое значение.`)
    .nullable();

export const planFields = z.object({
  name: z
    .string({ error: "Укажите название тарифа." })
    .trim()
    .min(1, "Укажите название тарифа.")
    .max(PLAN_NAME_MAX, `Название — не длиннее ${PLAN_NAME_MAX} символов.`),
  slug: z
    .string({ error: "Укажите slug." })
    .trim()
    .min(2, "Slug — от 2 до 40 символов.")
    .max(40, "Slug — от 2 до 40 символов.")
    .regex(SLUG_PATTERN, "Slug: только строчные латинские буквы, цифры и дефисы между ними."),
  description: z.string().trim().max(PLAN_DESCRIPTION_MAX, `Описание — не длиннее ${PLAN_DESCRIPTION_MAX} символов.`),
  audience: z.enum(PLAN_AUDIENCES),
  seats: z
    .object({
      min: z
        .int({ error: "Пользователей от: укажите целое число." })
        .min(1, "Пользователей от: не меньше 1.")
        .max(100_000),
      max: z.int({ error: "Пользователей до: укажите целое число или оставьте поле пустым." }).max(100_000).nullable(),
    })
    .nullable(),
  custom_pricing: z.boolean(),
  price_monthly: pricesSchema("Цена в месяц"),
  price_yearly: pricesSchema("Цена в год"),
  limits: z.object({
    meeting_minutes_per_month: limit("Минуты встреч в месяц", 1_000_000),
    file_manager_gb: limit("File Manager", 1_000_000),
    knowledge_base_mb: limit("База знаний", 100_000_000),
  }),
  capabilities: z.object(
    Object.fromEntries(PLAN_CAPABILITIES.map((c) => [c, z.boolean()])) as Record<
      (typeof PLAN_CAPABILITIES)[number],
      z.ZodBoolean
    >,
  ),
  features: z
    .array(
      z
        .string()
        .trim()
        .min(1, "Пустая строка в списке возможностей.")
        .max(PLAN_FEATURE_MAX, `Каждая возможность — не длиннее ${PLAN_FEATURE_MAX} символов.`),
    )
    .max(PLAN_FEATURES_MAX, `Не больше ${PLAN_FEATURES_MAX} возможностей.`),
  is_active: z.boolean(),
  is_featured: z.boolean(),
  sort_order: z
    .int({ error: "Порядок: укажите целое число." })
    .min(0, "Порядок — от 0 до 999.")
    .max(999, "Порядок — от 0 до 999."),
});

type PlanFields = z.infer<typeof planFields>;

/** A period is either free everywhere or paid everywhere; a plan free in one currency only is a mistake. */
function mixedZero(prices: Prices) {
  const zeros = CURRENCIES.filter((currency) => prices[currency] === 0).length;
  return zeros > 0 && zeros < CURRENCIES.length;
}

function checkPlan(plan: PlanFields, ctx: z.RefinementCtx) {
  if (plan.audience === "team" && !plan.seats)
    ctx.addIssue({
      code: "custom",
      path: ["seats", "min"],
      message: "Командному тарифу нужен диапазон пользователей.",
    });
  if (plan.seats && plan.seats.max !== null && plan.seats.max < plan.seats.min)
    ctx.addIssue({ code: "custom", path: ["seats", "max"], message: "«До» не может быть меньше «от»." });
  for (const period of ["price_monthly", "price_yearly"] as const) {
    // A plan with a price agreed by sales stores no price at all.
    const nonZero = CURRENCIES.find((c) => plan[period][c] !== 0);
    if (plan.custom_pricing && nonZero)
      ctx.addIssue({
        code: "custom",
        path: [period, nonZero],
        message: "У тарифа с ценой по договорённости цены должны быть нулевыми.",
      });
    else if (!plan.custom_pricing && mixedZero(plan[period]))
      ctx.addIssue({
        code: "custom",
        path: [period, CURRENCIES.find((c) => plan[period][c] === 0) ?? "RUB"],
        message: "Цена должна быть нулевой во всех валютах (бесплатный тариф) или больше нуля во всех.",
      });
  }
}

export const planDraftSchema = planFields.superRefine(checkPlan);
/** Shape check for PATCH; the merged plan is then checked again with `planDraftSchema`. */
export const planPatchSchema = planFields.partial().extend({ archived: z.boolean().optional() });
