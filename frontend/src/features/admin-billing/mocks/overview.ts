import {
  type BillingOverview,
  CURRENCIES,
  type Currency,
  type CurrencyOverview,
  type MonthRevenue,
  type PlatformTotals,
  TRANSACTION_STATUSES,
  type Transaction,
} from "../domain/contract";
import { buildPayouts } from "./payouts";
import { netMinor, store } from "./store";
import { type Customer, DAY, type RefundEvent } from "./types";

/** Paid subscriptions alive at `at`, and their monthly recurring revenue. */
function subscriptionsAt(customers: Customer[], at: number) {
  let count = 0;
  let mrr = 0;
  for (const customer of customers) {
    if (customer.signup > at || (customer.churned !== null && customer.churned <= at)) continue;
    count += 1;
    mrr += customer.monthly_minor;
  }
  return { count, mrr };
}

function churnRate(customers: Customer[], at: number) {
  const start = subscriptionsAt(customers, at - 30 * DAY).count;
  let lost = 0;
  for (const customer of customers)
    if (customer.churned !== null && customer.churned > at - 30 * DAY && customer.churned <= at) lost += 1;
  return start === 0 ? 0 : lost / start;
}

function lastTwelveMonths(now: number): MonthRevenue[] {
  const date = new Date(now);
  return Array.from({ length: 12 }, (_, i) => {
    const start = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - 11 + i, 1));
    const month = `${start.getUTCFullYear()}-${String(start.getUTCMonth() + 1).padStart(2, "0")}`;
    return { month, professional: 0, team: 0, enterprise: 0 };
  });
}

function currencyOverview(
  currency: Currency,
  customers: Customer[],
  transactions: Transaction[],
  refunds: RefundEvent[],
  now: number,
): CurrencyOverview {
  const date = new Date(now);
  const monthStart = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1);
  const prevMonthStart = Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - 1, 1);
  const prevMonthToDate = Math.min(prevMonthStart + (now - monthStart), monthStart);
  const months = lastTwelveMonths(now);
  const monthIndex = new Map(months.map((month, index) => [month.month, index]));
  const statuses = new Map(TRANSACTION_STATUSES.map((status) => [status, { count: 0, amount_minor: 0 }]));
  let revenueMonth = 0;
  let revenuePrevToDate = 0;
  let revenuePrev = 0;

  for (const transaction of transactions) {
    const at = Date.parse(transaction.created_at);
    const amount = netMinor(transaction);
    const row = monthIndex.get(transaction.created_at.slice(0, 7));
    if (row !== undefined) months[row][transaction.plan] += amount;
    if (at >= monthStart) revenueMonth += amount;
    else if (at >= prevMonthStart) {
      revenuePrev += amount;
      if (at < prevMonthToDate) revenuePrevToDate += amount;
    }
    const summary = at > now - 30 * DAY ? statuses.get(transaction.status) : undefined;
    if (summary) {
      summary.count += 1;
      summary.amount_minor += transaction.status === "refunded" ? transaction.refunded_minor : transaction.amount_minor;
    }
  }

  const current = subscriptionsAt(customers, now);
  const previous = subscriptionsAt(customers, now - 30 * DAY);
  const monthRefunds = refunds.filter((refund) => refund.at >= monthStart);
  const arpu = (subs: { count: number; mrr: number }) => (subs.count === 0 ? 0 : Math.round(subs.mrr / subs.count));

  return {
    currency,
    kpis: {
      mrr_minor: current.mrr,
      mrr_prev_minor: previous.mrr,
      arr_minor: current.mrr * 12,
      revenue_month_minor: revenueMonth,
      revenue_prev_month_to_date_minor: revenuePrevToDate,
      revenue_prev_month_minor: revenuePrev,
      active_subscriptions: current.count,
      active_subscriptions_prev: previous.count,
      arpu_minor: arpu(current),
      arpu_prev_minor: arpu(previous),
      refunds_month_minor: monthRefunds.reduce((sum, refund) => sum + refund.amount_minor, 0),
      refunds_month_count: monthRefunds.length,
    },
    revenue_by_month: months,
    payments_by_status: TRANSACTION_STATUSES.map((status) => ({
      status,
      ...(statuses.get(status) ?? { count: 0, amount_minor: 0 }),
    })),
    payouts: buildPayouts(currency, transactions, now),
  };
}

/** Money per currency (never converted or summed across currencies) plus platform-wide counts. */
export function getOverview(): BillingOverview {
  const { customers, transactions, refunds } = store();
  const now = Date.now();
  const all = [...transactions.values()];
  const current = subscriptionsAt(customers, now);
  const totals: PlatformTotals = {
    active_subscriptions: current.count,
    active_subscriptions_prev: subscriptionsAt(customers, now - 30 * DAY).count,
    free_accounts: 4_000 + current.count * 7,
    churn_rate: churnRate(customers, now),
    churn_rate_prev: churnRate(customers, now - 30 * DAY),
  };
  return {
    generated_at: new Date(now).toISOString(),
    totals,
    by_currency: CURRENCIES.map((currency) =>
      currencyOverview(
        currency,
        customers.filter((customer) => customer.currency === currency),
        all.filter((transaction) => transaction.currency === currency),
        refunds.filter((refund) => refund.currency === currency),
        now,
      ),
    ),
  };
}
