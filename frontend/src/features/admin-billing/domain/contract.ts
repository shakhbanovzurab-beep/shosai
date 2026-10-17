/**
 * Admin › Finance and billing API contract, shared by the slice's UI and its route handlers in
 * `src/features/admin-billing/server` (served at `/api/admin/billing/*`). They proxy to
 * `${BACKEND_API_URL}/v1/admin/billing/*` when it is set and fall back to an in-memory demo
 * (`src/features/admin-billing/server/store.ts`) otherwise.
 * Platform-wide: every customer, not the signed-in user. snake_case to match Pydantic; errors are
 * FastAPI's `{ "detail": string }`. Money is always in minor units (kopecks, cents) of its currency,
 * and amounts in different currencies are never added together or converted.
 */

import type { CardBrand } from "@/lib/card-brand";

/* ---------- Currencies and plans ---------- */

/** Plans are priced separately in each currency; a customer pays in the one they signed up in. */
export const CURRENCIES = ["RUB", "USD", "EUR"] as const;
export type Currency = (typeof CURRENCIES)[number];

export const PLANS = [
  { id: "basic", label: "Basic" },
  { id: "professional", label: "Professional" },
  { id: "team", label: "Team" },
  { id: "enterprise", label: "Enterprise" },
] as const;

export type PlanId = (typeof PLANS)[number]["id"];
/** Plans that bring revenue, in the order charts stack them. */
export type PaidPlanId = Exclude<PlanId, "basic">;
export const PAID_PLANS: readonly PaidPlanId[] = ["professional", "team", "enterprise"];

/* ---------- Transactions: GET /admin/billing/transactions?status=&period=&currency=&page= ---------- */

export const TRANSACTION_STATUSES = ["paid", "pending", "failed", "refunded"] as const;
/** `refunded` covers partial refunds too: compare `refunded_minor` with `amount_minor`. */
export type TransactionStatus = (typeof TRANSACTION_STATUSES)[number];

export const PERIODS = ["30d", "90d", "12m", "all"] as const;
export type Period = (typeof PERIODS)[number];

export type TransactionPaymentMethod =
  | { type: "card"; brand: CardBrand; last4: string }
  /** Система быстрых платежей (RUB only); `bank` is the payer's bank as reported by НСПК. */
  | { type: "sbp"; bank: string }
  /** Enterprise customers pay invoices by bank transfer. */
  | { type: "bank_transfer"; bank: string };

export type Transaction = {
  id: string;
  /** Invoice number, e.g. "LEO-2026-004812". */
  number: string;
  created_at: string;
  customer: { id: string; name: string; email: string };
  plan: PaidPlanId;
  /** Team is billed per seat; null for other plans. */
  seats: number | null;
  currency: Currency;
  /** In minor units of `currency`. */
  amount_minor: number;
  /** Total refunded so far in `currency`, 0 when nothing was; at most `amount_minor`. */
  refunded_minor: number;
  method: TransactionPaymentMethod;
  status: TransactionStatus;
  /** Why the provider declined the charge; only on `failed`. */
  failure_reason: string | null;
  /** Where to download the invoice; null when none was issued (failed charges). */
  invoice_url: string | null;
};

export type TransactionsQuery = {
  /** Omitted for every status. */
  status?: TransactionStatus;
  period: Period;
  /** Omitted for every currency. */
  currency?: Currency;
  /** 1-based. */
  page: number;
};

export type TransactionsResponse = {
  items: Transaction[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

/* ---------- Refund: POST /admin/billing/transactions/{id}/refund ---------- */

/**
 * Always in the transaction's own currency, up to what is still refundable
 * (`amount_minor - refunded_minor`); several partial refunds add up.
 */
export type RefundRequest = { amount_minor: number };
/** The updated transaction. */
export type RefundResponse = Transaction;

/* ---------- Overview: GET /admin/billing/overview ---------- */

/** Money KPIs for the customers paying in one currency. */
export type CurrencyKpis = {
  mrr_minor: number;
  mrr_prev_minor: number;
  /** MRR × 12. */
  arr_minor: number;
  /** Net of refunds, from the 1st of this month until now. */
  revenue_month_minor: number;
  /** The same days of last month, for a fair comparison. */
  revenue_prev_month_to_date_minor: number;
  /** All of last month. */
  revenue_prev_month_minor: number;
  active_subscriptions: number;
  active_subscriptions_prev: number;
  /** MRR per paying account. */
  arpu_minor: number;
  arpu_prev_minor: number;
  refunds_month_minor: number;
  refunds_month_count: number;
};

/** Counts that make sense across currencies. */
export type PlatformTotals = {
  active_subscriptions: number;
  active_subscriptions_prev: number;
  /** Accounts on the free plan; not counted in subscriptions or ARPU. */
  free_accounts: number;
  /** Share of paid subscriptions cancelled over the last 30 days, 0–1. */
  churn_rate: number;
  churn_rate_prev: number;
};

export type MonthRevenue = { month: string } & Record<PaidPlanId, number>;

export type StatusSummary = { status: TransactionStatus; count: number; amount_minor: number };

export type PayoutStatus = "scheduled" | "in_transit" | "paid";

export type Payout = {
  id: string;
  date: string;
  amount_minor: number;
  /** Provider commission withheld from this payout. */
  fee_minor: number;
  status: PayoutStatus;
};

export type Payouts = {
  /** Эквайрер, через которого идут платежи картой (и СБП) в этой валюте, например «TBank» или «lava.top». */
  provider: string;
  /** Masked settlement account, e.g. "АО «Т-Банк», р/с •• 4821". */
  account: string;
  /** Null when nothing is waiting to be paid out. */
  next: Payout | null;
  /** Latest first. */
  recent: Payout[];
};

/** Everything money-related for one currency; all amounts are in `currency`. */
export type CurrencyOverview = {
  currency: Currency;
  kpis: CurrencyKpis;
  /** Last 12 months, oldest first; `month` is "YYYY-MM". Net revenue per paid plan. */
  revenue_by_month: MonthRevenue[];
  /** Payments created over the last 30 days, one entry per status. */
  payments_by_status: StatusSummary[];
  payouts: Payouts;
};

export type BillingOverview = {
  generated_at: string;
  totals: PlatformTotals;
  /** One entry per currency in CURRENCIES order. */
  by_currency: CurrencyOverview[];
};
