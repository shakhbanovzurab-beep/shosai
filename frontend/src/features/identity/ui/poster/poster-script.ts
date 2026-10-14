/**
 * Сценарий афиши входа: одна связная планёрка питает все слои — реплики летят в поле сумбура, идут по ленте
 * расшифровки с именами, из них следуют факты и напоминания Leo. Слова — в каталоге `identityPoster`; здесь то,
 * что не переводится: кто какую реплику говорит, доли времени, цвета говорящих и время фактов.
 */
export const SPEAKERS = ["first", "second", "third", "fourth"] as const;

export type Speaker = (typeof SPEAKERS)[number];

/** Реплика и её автор, в порядке разговора; разговор во всех языках один и тот же. */
export const TALK = [
  ["line01", "first"],
  ["line02", "second"],
  ["line03", "third"],
  ["line04", "second"],
  ["line05", "fourth"],
  ["line06", "first"],
  ["line07", "third"],
  ["line08", "second"],
  ["line09", "first"],
  ["line10", "fourth"],
  ["line11", "third"],
  ["line12", "first"],
  ["line13", "second"],
  ["line14", "fourth"],
] as const satisfies readonly (readonly [string, Speaker])[];

export type TalkLine = (typeof TALK)[number][0];

/** Доля времени говорящего — итог разметки по голосам. */
export const SHARE: Record<Speaker, number> = { first: 0.34, second: 0.27, third: 0.22, fourth: 0.17 };

/** Цвет имени говорящего: приглушённые холодные тона, различимые на тёмной афише в любой теме. */
export const SPEAKER_TEXT: Record<Speaker, string> = {
  first: "text-indigo-300",
  second: "text-sky-300",
  third: "text-emerald-300",
  fourth: "text-rose-300",
};

/** Буква в кружке — того же тона, что имя в ленте. */
export const SPEAKER_CHIP: Record<Speaker, string> = SPEAKER_TEXT;

/** Факт и секунда встречи, на которой он прозвучал. */
export const FACTS = [
  ["deadline", 192],
  ["decision", 468],
  ["promise", 1265],
] as const;

/** Напоминание Leo и время, к которому оно относится (час и минута, UTC — так форматирует интерфейс). */
export const LEO_NOTES = [
  ["note1", 16, 45],
  ["note2", 18, 10],
  ["note3", 9, 30],
  ["note4", 19, 5],
] as const;

export type LeoNoteTime = (typeof LEO_NOTES)[number];

/** Отметка времени встречи вида 03:12. */
export function meetingClock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * Детерминированный генератор: первый кадр афиши одинаков при каждой загрузке, а период такой, что повтора не
 * увидеть. `Math.random` дал бы новый старт каждый раз.
 */
export function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

export const prefersReducedMotion = (): boolean => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
