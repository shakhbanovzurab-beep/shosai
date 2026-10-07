/* Russian formatting for the plans screen. Intl formatters are built once here, not per call. */

import { CURRENCIES, type Currency, type Prices, type PromoCode } from "./contract";

const moneyFormatters: Record<Currency, Intl.NumberFormat> = {
  RUB: new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }),
  USD: new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }),
  EUR: new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "EUR",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }),
};
const integer = new Intl.NumberFormat("ru-RU");
const compact = new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 });
const day = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** Minor units in a currency, e.g. (99000, "RUB") → «990 ₽», (1200, "USD") → «12 $». */
export const formatMoney = (minor: number, currency: Currency) => moneyFormatters[currency].format(minor / 100);
/** Every currency of a price, e.g. «990 ₽ · 12 $ · 11 €». */
export const formatPrices = (prices: Partial<Prices>) =>
  CURRENCIES.flatMap((currency) => {
    const amount = prices[currency];
    return amount === undefined ? [] : [formatMoney(amount, currency)];
  }).join(" · ");
export const formatInteger = (value: number) => integer.format(value);
/** Large counts such as tokens, e.g. 5 000 000 → «5 млн». */
export const formatCompact = (value: number) => compact.format(value);
/** A `YYYY-MM-DD` calendar day, e.g. «1 янв. 2026 г.». */
export const formatDay = (iso: string) => day.format(new Date(`${iso}T00:00:00Z`));

/* ---------- Form inputs: strings in, contract numbers out ---------- */

const MONEY_PATTERN = /^\d+(?:[.,]\d{1,2})?$/;
const INT_PATTERN = /^\d+$/;
const SPACES = /\s+/g;

/** «1 990,50» → 199050 minor units; NaN when it isn't an amount, so validation reports it. */
export function parseMoney(input: string): number {
  const value = input.replace(SPACES, "");
  if (!MONEY_PATTERN.test(value)) return Number.NaN;
  return Math.round(Number(value.replace(",", ".")) * 100);
}

/** An optional whole number: empty → null (no limit), otherwise the number or NaN. */
export function parseOptionalInt(input: string): number | null {
  const value = input.replace(SPACES, "");
  if (value === "") return null;
  return INT_PATTERN.test(value) ? Number(value) : Number.NaN;
}

export function parseInt10(input: string): number {
  const value = input.replace(SPACES, "");
  return INT_PATTERN.test(value) ? Number(value) : Number.NaN;
}

/** Minor units back to a form value, e.g. 199050 → «1990,5». */
export const moneyInput = (minor: number) => String(minor / 100).replace(".", ",");
export const optionalIntInput = (value: number | null) => (value === null ? "" : String(value));

/** When a promo code is valid, e.g. «с 1 нояб. 2026 г.» or «Бессрочно». */
export function validity(promo: PromoCode) {
  const { valid_from: from, valid_until: until } = promo;
  if (from && until) return `${formatDay(from)} — ${formatDay(until)}`;
  if (from) return `с ${formatDay(from)}`;
  if (until) return `до ${formatDay(until)}`;
  return "Бессрочно";
}
