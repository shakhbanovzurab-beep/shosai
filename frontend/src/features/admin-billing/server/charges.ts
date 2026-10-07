import type { PaidPlanId, Transaction } from "../domain/contract";
import { DECLINES } from "./pricing";
import type { Random } from "./random";
import { type Customer, DAY, HOUR, type RefundEvent } from "./types";

type Draft = Omit<Transaction, "id" | "number" | "invoice_url">;
type RefundDraft = { draft: Draft; at: number; amount_minor: number };

const CHURN_ODDS: Record<PaidPlanId, number> = { professional: 0.03, team: 0.018, enterprise: 0.006 };

/**
 * Monthly renewals for every customer inside the visible window: bank transfers clear in three days,
 * fresh card charges may still be processing, about 4.5 % are declined and retried once, and roughly
 * one paid charge in a hundred is later refunded (a third of those partially). Mutates `churned`.
 */
export function generateCharges(random: Random, customers: Customer[], now: number, windowStart: number) {
  const drafts: Draft[] = [];
  const refundDrafts: RefundDraft[] = [];

  const charge = (customer: Customer, at: number) => {
    const base = {
      created_at: new Date(at).toISOString(),
      customer: { id: customer.id, name: customer.name, email: customer.email },
      plan: customer.plan,
      seats: customer.seats,
      currency: customer.currency,
      amount_minor: customer.monthly_minor,
      refunded_minor: 0,
      method: customer.method,
      failure_reason: null,
    };
    if (customer.method.type === "bank_transfer") {
      drafts.push({ ...base, status: now - at < 3 * DAY ? "pending" : "paid" });
      return true;
    }
    if (now - at < 6 * HOUR && random.chance(0.35)) {
      drafts.push({ ...base, status: "pending" });
      return true;
    }
    if (random.chance(0.045)) {
      drafts.push({ ...base, status: "failed", failure_reason: random.pick(DECLINES) });
      return false;
    }
    const paid: Draft = { ...base, status: "paid" };
    drafts.push(paid);
    const roll = random.next();
    const refundAt = at + random.between(1, 6) * DAY;
    if (roll < 0.012 && refundAt < now) {
      const share = roll < 0.004 ? random.between(20, 60) / 100 : 1;
      refundDrafts.push({ draft: paid, at: refundAt, amount_minor: Math.round(customer.monthly_minor * share) });
    }
    return true;
  };

  for (const customer of customers) {
    const first = new Date(customer.signup);
    const day = Math.min(first.getUTCDate(), 28);
    for (let month = first.getUTCMonth(); ; month++) {
      const at = Date.UTC(first.getUTCFullYear(), month, day, first.getUTCHours(), random.between(0, 59));
      if (at > now) break;
      if (at < windowStart - 31 * DAY) continue;
      if (at > customer.signup + DAY && random.chance(CHURN_ODDS[customer.plan])) {
        customer.churned = at - random.between(1, 10) * DAY;
        break;
      }
      if (at < windowStart || charge(customer, at)) continue;
      // Declined: the provider retries two days later, otherwise the subscription lapses.
      const retry = at + 2 * DAY + random.between(0, 8) * HOUR;
      if (retry < now && random.chance(0.7)) charge(customer, retry);
      else {
        customer.churned = Math.min(retry, now - DAY);
        break;
      }
    }
  }

  return finalize(drafts, refundDrafts);
}

/** Orders charges by time, numbers their invoices per year and applies the refunds. */
function finalize(drafts: Draft[], refundDrafts: RefundDraft[]) {
  drafts.sort((a, b) => a.created_at.localeCompare(b.created_at));
  const transactions = new Map<string, Transaction>();
  const ids = new Map<Draft, string>();
  const sequence = new Map<number, number>();
  for (const draft of drafts) {
    const year = new Date(draft.created_at).getUTCFullYear();
    const n = (sequence.get(year) ?? 0) + 1;
    sequence.set(year, n);
    const id = `txn_${(1_000_000 + ids.size).toString(36)}`;
    ids.set(draft, id);
    transactions.set(id, {
      ...draft,
      id,
      number: `LEO-${year}-${String(n).padStart(6, "0")}`,
      invoice_url: draft.status === "failed" ? null : `/api/admin/billing/transactions/${id}/invoice`,
    });
  }

  const refunds: RefundEvent[] = [];
  for (const refund of refundDrafts) {
    const id = ids.get(refund.draft);
    const transaction = id ? transactions.get(id) : undefined;
    if (!transaction) continue;
    transactions.set(transaction.id, { ...transaction, status: "refunded", refunded_minor: refund.amount_minor });
    refunds.push({
      transaction_id: transaction.id,
      currency: transaction.currency,
      at: refund.at,
      amount_minor: refund.amount_minor,
    });
  }
  return { transactions, refunds };
}
