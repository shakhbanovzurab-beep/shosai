/*
 * Календарные дни без React: какой день у момента в поясе, сколько дней между двумя днями и как печатать день без
 * времени. Их считают домены срезов и хуки дат; пояс кабинета даёт `time-zone.ts`.
 */

const DAY_MS = 86_400_000;

/** Параметры форматтера для календарного дня без времени: он печатается в UTC, где лежит его полночь. */
export const CALENDAR_DAY = { timeZone: "UTC" } as const;

const dayFormats = new Map<string, Intl.DateTimeFormat>();

/** Календарный день момента в поясе: «2026-10-20». */
export function dayIn(moment: Date | number | string, zone: string): string {
  let format = dayFormats.get(zone);
  if (!format) {
    // Не для показа: только числа дня, латинскими цифрами при любом языке браузера.
    format = new Intl.DateTimeFormat(undefined, {
      timeZone: zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      numberingSystem: "latn",
    });
    dayFormats.set(zone, format);
  }
  const parts = Object.fromEntries(format.formatToParts(new Date(moment)).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

/** Сколько календарных дней от дня `from` до дня `to` (оба «2026-10-20»): 1 — следующий день, −1 — вчерашний. */
export const daysBetween = (from: string, to: string): number =>
  Math.round((Date.parse(to) - Date.parse(from)) / DAY_MS);

const DAY_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** Календарный день значения: день без времени («2026-10-20») — он сам, у момента — его день в поясе. */
export const dayOf = (value: string, zone: string): string => (DAY_ONLY.test(value) ? value : dayIn(value, zone));

const hourFormats = new Map<string, Intl.DateTimeFormat>();

/** Час момента (0–23) в поясе: по нему приветствие называет часть дня. */
export function hourIn(moment: Date | number | string, zone: string): number {
  let format = hourFormats.get(zone);
  if (!format) {
    format = new Intl.DateTimeFormat(undefined, {
      timeZone: zone,
      hour: "numeric",
      hourCycle: "h23",
      numberingSystem: "latn",
    });
    hourFormats.set(zone, format);
  }
  return Number(format.formatToParts(new Date(moment)).find((part) => part.type === "hour")?.value ?? 0);
}
