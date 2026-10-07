const numberFormat = new Intl.NumberFormat("ru-RU");
const compactFormat = new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 });
const percentFormat = new Intl.NumberFormat("ru-RU", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const fullDateTimeFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "long", timeStyle: "medium" });
const timeFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dayFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
const hourFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const dayRelative = new Intl.RelativeTimeFormat("ru-RU", { numeric: "auto" });

export const formatNumber = (value: number) => numberFormat.format(value);
export const formatCompact = (value: number) => compactFormat.format(value);
export const formatPercent = (value: number) => percentFormat.format(value);
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso));
export const formatFullDateTime = (iso: string) => fullDateTimeFormat.format(new Date(iso));
export const formatTime = (iso: string) => timeFormat.format(new Date(iso));
export const formatBucket = (iso: string, bucket: "hour" | "day") =>
  (bucket === "hour" ? hourFormat : dayFormat).format(new Date(iso));

/** «только что», «5 мин назад», «3 ч назад», «вчера», «4 дня назад», then the date. */
export function formatRelative(iso: string, now = Date.now()) {
  const minutes = Math.round((now - Date.parse(iso)) / 60_000);
  if (minutes < 1) return "только что";
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.round(hours / 24);
  if (days < 7) return dayRelative.format(-days, "day");
  return dayFormat.format(new Date(iso));
}

/** Change against the previous period as a signed percentage, or null when there was nothing before. */
export function percentChange(current: number, previous: number) {
  if (previous === 0) return null;
  return (current - previous) / previous;
}
