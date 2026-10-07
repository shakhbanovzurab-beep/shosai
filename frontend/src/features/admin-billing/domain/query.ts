import {
  CURRENCIES,
  type Currency,
  PERIODS,
  type Period,
  TRANSACTION_STATUSES,
  type TransactionStatus,
  type TransactionsQuery,
} from "./contract";

export const DEFAULT_PERIOD: Period = "30d";
export const PAGE_SIZE = 20;

const isStatus = (value: string | null): value is TransactionStatus =>
  TRANSACTION_STATUSES.some((status) => status === value);
const isPeriod = (value: string | null): value is Period => PERIODS.some((period) => period === value);
export const isCurrency = (value: string | null): value is Currency =>
  CURRENCIES.some((currency) => currency === value);

/** Reads `?status=&period=&currency=&page=`, falling back to defaults for anything missing or unknown. */
export function parseTransactionsQuery(params: { get: (name: string) => string | null }): TransactionsQuery {
  const status = params.get("status");
  const period = params.get("period");
  const currency = params.get("currency");
  const page = Number.parseInt(params.get("page") ?? "", 10);
  return {
    status: isStatus(status) ? status : undefined,
    period: isPeriod(period) ? period : DEFAULT_PERIOD,
    currency: isCurrency(currency) ? currency : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

/** The query string for a query, leaving out defaults so URLs stay short. */
export function transactionsSearch(query: TransactionsQuery): string {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.period !== DEFAULT_PERIOD) params.set("period", query.period);
  if (query.currency) params.set("currency", query.currency);
  if (query.page > 1) params.set("page", String(query.page));
  const search = params.toString();
  return search ? `?${search}` : "";
}
