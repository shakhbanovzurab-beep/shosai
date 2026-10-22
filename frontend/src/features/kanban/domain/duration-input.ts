import { parseNumberInput } from "./number-input";

/*
 * Длительность, набранная человеком: часы (можно с дробью — «1,5») и минуты, цифрами любой письменности кабинета.
 * Слов-единиц разбор не знает: единицы подписаны у полей, поэтому ввод одинаков на всех языках.
 */

/** Минуты; оба поля пустые — null; не число, меньше нуля или больше `max` — undefined. */
export function minutesFromInput(
  hours: string,
  minutes: string,
  locale: string,
  max: number,
): number | null | undefined {
  if (!hours.trim() && !minutes.trim()) return null;
  const h = hours.trim() ? parseNumberInput(hours, locale) : 0;
  const m = minutes.trim() ? parseNumberInput(minutes, locale) : 0;
  if (h === null || m === null || h < 0 || m < 0) return undefined;
  const total = Math.round(h * 60 + m);
  return total > max ? undefined : total;
}

/** Набранная длительность: часы и минуты как текст — человек может набрать «1,5» или «٢». */
export type DurationDraft = { hours: string; minutes: string };

/** Длительность в минутах — как её показать в полях, цифрами языка человека; null — пусто. */
export function draftOf(minutes: number | null, locale: string): DurationDraft {
  if (minutes === null) return { hours: "", minutes: "" };
  const number = new Intl.NumberFormat(locale, { useGrouping: false });
  return { hours: number.format(Math.floor(minutes / 60)), minutes: number.format(minutes % 60) };
}
