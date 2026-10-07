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
