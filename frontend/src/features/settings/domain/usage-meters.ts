/*
 * Шкалы единого вида использования (Settings › Usage и Upgrade): сколько израсходовано и насколько это близко
 * к лимиту. О лимите говорят там, где он мешает, а не потоком напоминаний: тон решает цвет и слова строки
 * и то, насколько заметна кнопка тарифов.
 */

/** В норме, заканчивается (от `LOW_AT`), исчерпано. */
export type MeterTone = "ok" | "low" | "full";

/** Что считает строка: токены двух уровней, минуты встреч месяца, хранилище File Manager и файлы для Leo. */
export type UsageKind = "standard" | "frontier" | "minutes" | "storage" | "knowledge";

export const LOW_AT = 0.8;

const RANK: Record<MeterTone, number> = { ok: 0, low: 1, full: 2 };

/** Доля для полосы (null — лимита нет) и тон. Лимит 0 — «не входит в план»: такую строку не показывают. */
export function meterStanding(used: number, limit: number | null): { share: number | null; tone: MeterTone } {
  if (limit === null) return { share: null, tone: "ok" };
  const share = limit > 0 ? Math.min(1, used / limit) : 1;
  if (share >= 1) return { share, tone: "full" };
  return { share, tone: share >= LOW_AT ? "low" : "ok" };
}

/**
 * Frontier-модели: исчерпанная неделя при купленных токенах — не остановка, а «идут купленные», поэтому тон
 * не выше «заканчивается».
 */
export function frontierStanding(used: number, limit: number | null, extraTokens: number) {
  const standing = meterStanding(used, limit);
  return standing.tone === "full" && extraTokens > 0 ? { ...standing, tone: "low" as const } : standing;
}

/** Самый тревожный тон из строк — им говорит кнопка тарифов. */
export function worstTone(tones: readonly MeterTone[]): MeterTone {
  return tones.reduce<MeterTone>((worst, tone) => (RANK[tone] > RANK[worst] ? tone : worst), "ok");
}
