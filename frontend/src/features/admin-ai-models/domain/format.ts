/** Russian number, money and date formatting for Admin › AI-модели. Money is in USD. */

const usd = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const usdPrice = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});
const compact = new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat("ru-RU");
const percent = new Intl.NumberFormat("ru-RU", { style: "percent", maximumFractionDigits: 0 });
const shortDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", timeZone: "UTC" });
const longDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", weekday: "short", timeZone: "UTC" });
const times = new Map<string, Intl.DateTimeFormat>();

export const formatUsd = (value: number) => usd.format(value);
export const formatPrice = (value: number) => usdPrice.format(value);
export const formatCompact = (value: number) => compact.format(value);
export const formatInteger = (value: number) => integer.format(value);
export const formatPercent = (value: number) => percent.format(value);
/** "5 окт." from an ISO date (YYYY-MM-DD). */
export const formatShortDate = (iso: string) => shortDate.format(new Date(`${iso}T00:00:00Z`));
/** "вс, 5 октября" from an ISO date (YYYY-MM-DD). */
export const formatLongDate = (iso: string) => longDate.format(new Date(`${iso}T00:00:00Z`));
/** «14:05:30 МСК»: время в деловом поясе платформы с его подписью (ADR 0058). */
export function formatTime(iso: string, zone: string, label: string) {
  let time = times.get(zone);
  if (time === undefined) {
    time = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: zone });
    times.set(zone, time);
  }
  return `${time.format(new Date(iso))} ${label}`;
}
