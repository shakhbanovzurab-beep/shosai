import type { Transaction, TransactionsQuery, TransactionsResponse } from "../domain/contract";
import { formatMoney } from "../domain/format";
import { PAGE_SIZE } from "../domain/query";
import { store } from "./store";
import { DAY } from "./types";

const PERIOD_DAYS = { "30d": 30, "90d": 90, "12m": 365 } as const;

/** Latest first, filtered by status, period and currency, one page of PAGE_SIZE. */
export function listTransactions(query: TransactionsQuery): TransactionsResponse {
  const since = query.period === "all" ? 0 : Date.now() - PERIOD_DAYS[query.period] * DAY;
  const matching: Transaction[] = [];
  for (const transaction of store().transactions.values()) {
    if (query.status && transaction.status !== query.status) continue;
    if (query.currency && transaction.currency !== query.currency) continue;
    if (Date.parse(transaction.created_at) < since) continue;
    matching.push(transaction);
  }
  matching.reverse();
  const totalPages = Math.max(1, Math.ceil(matching.length / PAGE_SIZE));
  const page = Math.min(query.page, totalPages);
  return {
    items: matching.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    page,
    page_size: PAGE_SIZE,
    total: matching.length,
    total_pages: totalPages,
  };
}

export const getTransaction = (id: string) => store().transactions.get(id) ?? null;

export type RefundResult =
  | { ok: true; transaction: Transaction }
  | { ok: false; status: 404 | 409 | 422; message: string };

/** Refunds part or all of what is left on a settled payment, in the payment's own currency. */
export function refundTransaction(id: string, amountMinor: number): RefundResult {
  const data = store();
  const transaction = data.transactions.get(id);
  if (!transaction) return { ok: false, status: 404, message: "Платёж не найден." };
  if (transaction.status !== "paid" && transaction.status !== "refunded")
    return { ok: false, status: 409, message: "Вернуть можно только оплаченный платёж." };
  const refundable = transaction.amount_minor - transaction.refunded_minor;
  if (refundable <= 0) return { ok: false, status: 409, message: "Платёж уже возвращён полностью." };
  if (amountMinor > refundable) {
    const limit = formatMoney(refundable, transaction.currency);
    return { ok: false, status: 422, message: `Сумма возврата больше доступной — ${limit}.` };
  }
  const next: Transaction = {
    ...transaction,
    status: "refunded",
    refunded_minor: transaction.refunded_minor + amountMinor,
  };
  data.transactions.set(id, next);
  data.refunds.push({ transaction_id: id, currency: next.currency, at: Date.now(), amount_minor: amountMinor });
  return { ok: true, transaction: next };
}
