import { pluralizeRu } from "@/lib/plural";

/* Russian formatting for the LiveKit dashboard; formatters are created once per module. */

const integer = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const timeFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const timeWithSeconds = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const MINUTE = 60_000;

export const formatInteger = (value: number) => integer.format(value);
/** Значение или «—», когда Prometheus не дал данных. */
export const orNoData = (value: number | null, format: (value: number) => string) =>
  value === null ? NO_DATA : format(value);
export const NO_DATA = "—";
export const formatPercent = (value: number) => `${integer.format(value)} %`;
export const formatMbps = (value: number) => `${decimal.format(value)} Мбит/с`;
export const formatTime = (iso: string) => timeFormat.format(new Date(iso));
export const formatClock = (iso: string) => timeWithSeconds.format(new Date(iso));
export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));

export const participantsLabel = (count: number) =>
  `${integer.format(count)} ${pluralizeRu(count, ["участник", "участника", "участников"])}`;

/** Time between two instants, e.g. "12 дн 5 ч", "1 ч 04 мин", "7 мин". */
export function formatDuration(fromIso: string, toIso: string) {
  const minutes = Math.max(0, Math.floor((Date.parse(toIso) - Date.parse(fromIso)) / MINUTE));
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const rest = minutes % 60;
  if (days > 0) return `${days} дн ${hours} ч`;
  if (hours > 0) return `${hours} ч ${String(rest).padStart(2, "0")} мин`;
  return minutes < 1 ? "меньше минуты" : `${rest} мин`;
}

const BYTE_UNITS = [
  [1024 ** 3, "ГБ"],
  [1024 ** 2, "МБ"],
  [1024, "КБ"],
] as const;

export function formatBytes(bytes: number) {
  for (const [size, unit] of BYTE_UNITS) if (bytes >= size) return `${decimal.format(bytes / size)} ${unit}`;
  return `${integer.format(bytes)} Б`;
}
