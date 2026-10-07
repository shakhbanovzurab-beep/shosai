const numberFormat = new Intl.NumberFormat("ru-RU");
const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", year: "numeric" });
const fullDateTimeFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "long", timeStyle: "short" });
const dayRelative = new Intl.RelativeTimeFormat("ru-RU", { numeric: "auto" });
const megabytes = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

export const formatNumber = (value: number) => numberFormat.format(value);
export const formatDate = (iso: string) => dateFormat.format(new Date(iso));
export const formatFullDateTime = (iso: string) => fullDateTimeFormat.format(new Date(iso));

const moneyFormats = new Map<string, Intl.NumberFormat>();

/** "$400", "$1 920": whole currency units, the way plans are priced. */
export function formatMoney(cents: number, currency: string) {
  let format = moneyFormats.get(currency);
  if (!format) {
    format = new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: 0 });
    moneyFormats.set(currency, format);
  }
  return format.format(cents / 100);
}

/** «только что», «5 мин назад», «3 ч назад», «вчера», «4 дня назад», then the date. */
export function formatRelative(iso: string, now = Date.now()) {
  const minutes = Math.round((now - Date.parse(iso)) / 60_000);
  if (minutes < 1) return "только что";
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.round(hours / 24);
  if (days < 7) return dayRelative.format(-days, "day");
  return formatDate(iso);
}

/** «через 9 дней», «завтра»: when a trial ends. */
export function formatUntil(iso: string, now = Date.now()) {
  const days = Math.max(0, Math.ceil((Date.parse(iso) - now) / 86_400_000));
  return dayRelative.format(days, "day");
}

/** "1,2 МБ": knowledge size in the units people expect. */
export function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${formatNumber(Math.round(bytes / 1024))} КБ`;
  return `${megabytes.format(bytes / 1024 / 1024)} МБ`;
}

/** Russian plural forms: plural(3, ["место", "места", "мест"]) → "3 места". */
export function plural(n: number, [one, few, many]: [string, string, string]) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  let word = many;
  if (mod10 === 1 && mod100 !== 11) word = one;
  else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) word = few;
  return `${formatNumber(n)} ${word}`;
}
