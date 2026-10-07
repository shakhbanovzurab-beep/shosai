import { z } from "zod";

import { CURRENCIES, PERIODS, TRANSACTION_STATUSES } from "./contract";
import { DEFAULT_PERIOD } from "./query";

/*
 * Request validation for the billing routes. Kept apart from `query.ts` and `refund.ts`, which the
 * browser imports too, so zod stays out of the page's bundle.
 */

/** `GET /admin/billing/transactions?status=&period=&currency=&page=`; empty parameters count as missing. */
export const transactionsQuerySchema = z.object({
  status: z.enum(TRANSACTION_STATUSES).optional(),
  period: z.enum(PERIODS).default(DEFAULT_PERIOD),
  currency: z.enum(CURRENCIES).optional(),
  page: z.coerce.number().int().min(1).default(1),
});

/** `POST /admin/billing/transactions/{id}/refund`. */
export const refundRequestSchema = z.object({
  amount_minor: z.number().int("Сумма возврата — целое число копеек.").positive("Укажите сумму больше нуля."),
});
