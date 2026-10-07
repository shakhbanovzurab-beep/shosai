/* Russian date and size formatting for the support inbox; formatters are created once. */

const timeFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const weekdayFormat = new Intl.DateTimeFormat("ru-RU", { weekday: "short" });
const shortDateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
const longDateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" });
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});
const dayFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", weekday: "long" });
const sizeFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

const DAY_MS = 86_400_000;

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

/** List timestamps: time today, weekday this week, otherwise the date. */
export function formatListTime(iso: string, now = new Date()) {
  const date = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY_MS);
  if (days <= 0) return timeFormat.format(date);
  if (days < 7) return weekdayFormat.format(date);
  return shortDateFormat.format(date);
}

export const formatTime = (iso: string) => timeFormat.format(new Date(iso));
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso));
export const formatLongDate = (iso: string) => longDateFormat.format(new Date(iso));
export const formatShortDate = (iso: string) => shortDateFormat.format(new Date(iso));

/** «Сегодня», «Вчера» or «пятница, 3 октября» for day separators in a thread. */
export function formatDay(iso: string, now = new Date()) {
  const days = Math.round((startOfDay(now) - startOfDay(new Date(iso))) / DAY_MS);
  if (days === 0) return "Сегодня";
  if (days === 1) return "Вчера";
  return dayFormat.format(new Date(iso));
}

export const dayKey = (iso: string) => startOfDay(new Date(iso));

export function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${sizeFormat.format(Math.max(1, bytes / 1024))} КБ`;
  return `${sizeFormat.format(bytes / 1024 / 1024)} МБ`;
}
