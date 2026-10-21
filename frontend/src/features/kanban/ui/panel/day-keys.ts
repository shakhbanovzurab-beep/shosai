/* Клетки календаря — местные дни браузера: читаются и создаются местными геттерами, как велит docs/i18n.md. */

const pad = (value: number) => String(value).padStart(2, "0");

/** Местный день ячейки календаря → "2026-10-21". */
export const dayKeyOf = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

/** "2026-10-21" → местная полночь этого дня для календаря. */
export function localDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date);
}
