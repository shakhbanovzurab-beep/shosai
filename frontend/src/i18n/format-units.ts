/*
 * Sizes and durations in the interface language, through Intl units: "3.2 MB" / "3,2 МБ", "4.2 sec" /
 * "4,2 с" / "4.2 秒". Formatters are cached per language and shape.
 */

const KB = 1024;
const MB = KB * 1024;
const GB = MB * 1024;

const cache = new Map<string, Intl.NumberFormat>();

// "short" everywhere: "narrow" falls back to Latin letters in some languages (Japanese "4.2s" instead of 秒).
function unitFormat(locale: string, unit: string, fractionDigits: number) {
  const key = `${locale}|${unit}|${fractionDigits}`;
  let format = cache.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale, {
      style: "unit",
      unit,
      unitDisplay: "short",
      maximumFractionDigits: fractionDigits,
    });
    cache.set(key, format);
  }
  return format;
}

/** A file size for people: "512 byte", "48 kB", "3.2 MB", "1.8 GB" (binary steps, as file managers count). */
export function formatBytes(locale: string, bytes: number): string {
  if (bytes < KB) return unitFormat(locale, "byte", 0).format(bytes);
  if (bytes < MB) return unitFormat(locale, "kilobyte", 0).format(bytes / KB);
  if (bytes < GB) return unitFormat(locale, "megabyte", 1).format(bytes / MB);
  return unitFormat(locale, "gigabyte", 1).format(bytes / GB);
}

/** How long something took: "4.2 sec" under ten seconds, "42 sec", then minutes and seconds, "1 min 5 sec". */
export function formatDuration(locale: string, ms: number): string {
  if (ms < 60_000) return unitFormat(locale, "second", ms < 10_000 ? 1 : 0).format(ms / 1000);
  const minutes = unitFormat(locale, "minute", 0).format(Math.floor(ms / 60_000));
  const seconds = unitFormat(locale, "second", 0).format(Math.round((ms % 60_000) / 1000));
  return new Intl.ListFormat(locale, { type: "unit", style: "narrow" }).format([minutes, seconds]);
}

const SPAN_UNITS = [
  ["days", "day", 86_400_000],
  ["hours", "hour", 3_600_000],
  ["minutes", "minute", 60_000],
  ["seconds", "second", 1000],
] as const;

type SpanPart = (typeof SPAN_UNITS)[number][0];

const spanCache = new Map<string, Intl.DurationFormat>();

function spanFormat(locale: string, always: boolean) {
  const key = `${locale}|${always}`;
  let format = spanCache.get(key);
  if (!format) {
    format = new Intl.DurationFormat(locale, { style: "short", minutesDisplay: always ? "always" : "auto" });
    spanCache.set(key, format);
  }
  return format;
}

/**
 * Промежуток времени для людей — две старшие части, до `smallest`: «3 дн. 4 ч», «2 ч 15 мин», «0 мин». Слова и
 * связки — языка (Intl.DurationFormat); где его нет, части собираются единицами и списком. Знак не печатается.
 */
export function formatSpan(locale: string, ms: number, smallest: "minute" | "second" = "minute"): string {
  const last = SPAN_UNITS.findIndex(([, unit]) => unit === smallest);
  let rest = Math.abs(ms);
  const parts: [SpanPart, string, number][] = [];
  for (const [part, unit, size] of SPAN_UNITS.slice(0, last + 1)) {
    const amount = Math.floor(rest / size);
    rest -= amount * size;
    if (amount > 0 || parts.length > 0) parts.push([part, unit, amount]);
  }
  const shown = parts.slice(0, 2).filter(([, , amount], index) => index === 0 || amount > 0);
  if (shown.length === 0) shown.push(smallest === "minute" ? ["minutes", "minute", 0] : ["seconds", "second", 0]);
  if (typeof Intl.DurationFormat !== "function")
    return new Intl.ListFormat(locale, { type: "unit", style: "narrow" }).format(
      shown.map(([, unit, amount]) => unitFormat(locale, unit, 0).format(amount)),
    );
  const zero = shown.length === 1 && shown[0]?.[2] === 0;
  return spanFormat(locale, zero).format(Object.fromEntries(shown.map(([part, , amount]) => [part, amount])));
}

const clockCache = new Map<string, Intl.DurationFormat>();

/** Идущие часы с секундами: «1:05:03», от суток — с днями, «1 дн. 6:00:12». Знак не печатается. */
export function formatClock(locale: string, ms: number): string {
  const total = Math.floor(Math.abs(ms) / 1000);
  const parts = {
    days: Math.floor(total / 86_400),
    hours: Math.floor((total % 86_400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
  if (typeof Intl.DurationFormat !== "function") {
    const two = new Intl.NumberFormat(locale, { minimumIntegerDigits: 2 });
    const clock = `${parts.hours}:${two.format(parts.minutes)}:${two.format(parts.seconds)}`;
    return parts.days > 0 ? `${unitFormat(locale, "day", 0).format(parts.days)} ${clock}` : clock;
  }
  let format = clockCache.get(locale);
  if (!format) {
    format = new Intl.DurationFormat(locale, { style: "digital", hoursDisplay: "always" });
    clockCache.set(locale, format);
  }
  return format.format(parts);
}

/** Короткое название единицы на языке человека — подпись поля ввода: «ч», «мин», «hr», «min». */
export function unitLabel(locale: string, unit: "hour" | "minute"): string {
  return unitFormat(locale, unit, 0)
    .formatToParts(2)
    .filter((part) => part.type === "unit")
    .map((part) => part.value)
    .join("");
}
