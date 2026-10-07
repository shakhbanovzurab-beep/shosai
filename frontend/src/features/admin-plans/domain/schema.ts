import { z } from "zod";

import { CURRENCIES, CURRENCY_SYMBOL, type Currency, PRICE_MAX } from "./contract";

/* Helpers shared by the plan and promo code schemas, the route handlers and the admin forms. */

/** An amount in minor units; the label names the field and currency in error messages. */
export const money = (label: string, minimum = 0) =>
  z
    .int({ error: `${label}: укажите сумму.` })
    .min(
      minimum,
      minimum > 0 ? `${label}: не меньше ${minimum / 100}.` : `${label}: сумма не может быть отрицательной.`,
    )
    .max(PRICE_MAX, `${label}: не больше 10 000 000.`);

/** One required amount per currency, e.g. «Цена в месяц, $». */
export const pricesSchema = (label: string) =>
  z.object(
    Object.fromEntries(CURRENCIES.map((c) => [c, money(`${label}, ${CURRENCY_SYMBOL[c]}`)])) as Record<
      Currency,
      ReturnType<typeof money>
    >,
  );

/** The first problem, for an API `{ detail }` answer. */
export const firstIssue = (error: z.ZodError, fallback: string) => error.issues[0]?.message ?? fallback;

/** One message per field, keyed by dotted path (`limits.file_manager_gb`, `price_monthly.USD`), for form inputs. */
export function issuesByField(error: z.ZodError): Record<string, string> {
  const result: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = issue.path.join(".");
    result[key] ??= issue.message;
  }
  return result;
}
