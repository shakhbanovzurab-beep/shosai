/* Russian (ru-RU) money, date and percent formatting for Admin › Finance, in the UI and the API routes alike. */

import type { Currency } from "./contract";

type MoneyStyle = "exact" | "whole" | "compact";
const MONEY_OPTIONS: Record<MoneyStyle, Intl.NumberFormatOptions> = {
  exact: { minimumFractionDigits: 2, maximumFractionDigits: 2 },
  whole: { maximumFractionDigits: 0 },
  compact: { notation: "compact", maximumFractionDigits: 1 },
};
// Intl formatters are expensive to build: one per currency and style, created on first use and reused.
const moneyFormatters = new Map<string, Intl.NumberFormat>();
function moneyFormatter(currency: Currency, style: MoneyStyle) {
  const key = `${currency}:${style}`;
  let formatter = moneyFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat("ru-RU", { style: "currency", currency, ...MONEY_OPTIONS[style] });
    moneyFormatters.set(key, formatter);
  }
  return formatter;
}

const integer = new Intl.NumberFormat("ru-RU");
const percent = new Intl.NumberFormat("ru-RU", { style: "percent", maximumFractionDigits: 1 });
const signedPercent = new Intl.NumberFormat("ru-RU", {
  style: "percent",
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});
const signedPoints = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1, signDisplay: "exceptZero" });
const decimalInput = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const day = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const dayShort = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", timeZone: "UTC" });
const time = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
const monthShort = new Intl.DateTimeFormat("ru-RU", { month: "short", timeZone: "UTC" });
const monthLong = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric", timeZone: "UTC" });

/** (199000, "RUB") → "1 990 ₽", (1250, "USD") → "12,50 $"; minor units are shown only when there are any. */
export const formatMoney = (minor: number, currency: Currency) =>
  moneyFormatter(currency, minor % 100 === 0 ? "whole" : "exact").format(minor / 100);

/** (125000000, "RUB") → "1,3 млн ₽" */
export const formatMoneyCompact = (minor: number, currency: Currency) =>
  moneyFormatter(currency, "compact").format(minor / 100);

export const CURRENCY_SYMBOLS: Record<Currency, string> = { RUB: "₽", USD: "$", EUR: "€" };
export const CURRENCY_NAMES: Record<Currency, string> = { RUB: "Рубли", USD: "Доллары", EUR: "Евро" };

/** 1234 → "1 234" */
export const formatInteger = (value: number) => integer.format(value);

/** 0.0342 → "3,4 %" */
export const formatPercent = (ratio: number) => percent.format(ratio);

/** 0.12 → "+12 %" */
export const formatChange = (ratio: number) => signedPercent.format(ratio);

/** Difference of two ratios in percentage points: 0.004 → "+0,4 п. п." */
export const formatPointsChange = (difference: number) => `${signedPoints.format(difference * 100)} п. п.`;

/** 150050 → "1 500,50", for prefilling an amount input. */
export const formatAmountInput = (minor: number) => decimalInput.format(minor / 100);

/** "5 окт. 2026 г." */
export const formatDay = (iso: string) => day.format(new Date(iso));

/** "5 октября" */
export const formatDayMonth = (iso: string) => dayShort.format(new Date(iso));

/** "14:05" (UTC, like the rest of the admin dates) */
export const formatTime = (iso: string) => time.format(new Date(iso));

/** "2026-10" → "окт." */
export const formatMonthShort = (month: string) => monthShort.format(new Date(`${month}-01T00:00:00Z`));

/** "2026-10" → "октябрь 2026 г." */
export const formatMonthLong = (month: string) => monthLong.format(new Date(`${month}-01T00:00:00Z`));

const SPACES = /[\s  ]/g;
const AMOUNT = /^\d+(?:[.,]\d{1,2})?$/;

/** "1 500,5" → 150050 minor units; null when it isn't a positive amount with at most two decimals. */
export function parseAmountInput(value: string): number | null {
  const compact = value.replace(SPACES, "");
  if (!AMOUNT.test(compact)) return null;
  const minor = Math.round(Number(compact.replace(",", ".")) * 100);
  return minor > 0 ? minor : null;
}

/** Relative change between two values; null when there is nothing to compare against. */
export const change = (current: number, previous: number) => (previous === 0 ? null : current / previous - 1);
