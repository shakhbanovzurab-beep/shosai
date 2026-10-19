/*
 * Источники ответа Leo: «каждый ответ называет свои источники и пространство, откуда каждый» (ADR 0039 §7).
 * Формат — предложение для решения владельца: событие `sources` в потоке и маркеры `[n]` в тексте ответа;
 * пока его отдают только моки разработки.
 */

export type SourceKind = "meeting" | "file" | "note" | "mail" | "web";

export type LeoSource = {
  id: string;
  kind: SourceKind;
  title: string;
  /** Пространство, откуда источник: «Personal» или имя workspace. */
  space: string;
  /** Где внутри: время в записи, страница; null — без места. */
  locator: string | null;
  /** Тот отрывок, на который опирается ответ. */
  quote: string;
  /** Слова отрывка, которые подтверждают ответ, — выделяются. */
  highlight: string[];
};

/** Предложение ответа и номера источников (с единицы), на которые оно ссылается. */
export type CitedSentence = { text: string; cites: number[] };

const MARKER = /\[(\d{1,2})\]/g;
const LEADING_MARKERS = /^(\s*\[\d{1,2}\])+/;

/** Номера из маркеров, только существующих источников: выдуманная ссылка просто не рисуется. */
function citesOf(text: string, sourceCount: number): number[] {
  const numbers = [...text.matchAll(MARKER)].map((match) => Number(match[1]));
  return [...new Set(numbers)].filter((n) => n >= 1 && n <= sourceCount);
}

/**
 * Делит абзац на предложения и отдаёт каждому его маркеры. Маркер, стоящий после точки («…звонок. [1] Дальше»),
 * относится к предыдущему предложению. Границы предложений — по `Intl.Segmenter` языка ответа.
 */
export function citedSentences(paragraph: string, sourceCount: number, locale: string): CitedSentence[] {
  const segmenter = new Intl.Segmenter(locale, { granularity: "sentence" });
  const sentences: CitedSentence[] = [];
  for (const { segment } of segmenter.segment(paragraph)) {
    const leading = segment.match(LEADING_MARKERS)?.[0] ?? "";
    const previous = sentences.at(-1);
    if (leading && previous) previous.cites = [...new Set([...previous.cites, ...citesOf(leading, sourceCount)])];
    const rest = leading ? segment.slice(leading.length).trimStart() : segment;
    if (rest.trim() === "") continue;
    sentences.push({
      text: rest.replace(MARKER, "").replace(/\s+([.,;:!?])/g, "$1"),
      cites: citesOf(rest, sourceCount),
    });
  }
  return sentences;
}

export type QuotePart = { text: string; at: number; lit: boolean };

/** Фразы по первой букве, длинные раньше коротких: на каждой позиции отрывка сравниваются только подходящие. */
function phrasesByFirstLetter(highlight: readonly string[]): Map<string, string[]> {
  const byFirst = new Map<string, string[]>();
  for (const phrase of highlight.map((h) => h.toLowerCase()).toSorted((a, b) => b.length - a.length)) {
    if (phrase.length === 0) continue;
    const first = phrase.charAt(0);
    byFirst.set(first, [...(byFirst.get(first) ?? []), phrase]);
  }
  return byFirst;
}

function phraseAt(quote: string, at: number, candidates: readonly string[]): string | null {
  for (const phrase of candidates) {
    if (quote.slice(at, at + phrase.length).toLowerCase() === phrase) return phrase;
  }
  return null;
}

/**
 * Отрывок, разбитый на части: `lit` — слова, подтверждающие ответ; `at` — начало части в отрывке, ключ для списка.
 * Поиск — простым сравнением без регулярного выражения из пришедших слов; при совпадении в одном месте берётся
 * самая длинная фраза.
 */
export function quoteParts(quote: string, highlight: readonly string[]): QuotePart[] {
  const byFirst = phrasesByFirstLetter(highlight);
  const parts: QuotePart[] = [];
  let start = 0;
  let at = 0;
  while (at < quote.length) {
    const candidates = byFirst.get(quote.charAt(at).toLowerCase());
    const hit = candidates ? phraseAt(quote, at, candidates) : null;
    if (hit === null) {
      at += 1;
      continue;
    }
    if (at > start) parts.push({ text: quote.slice(start, at), at: start, lit: false });
    parts.push({ text: quote.slice(at, at + hit.length), at, lit: true });
    at += hit.length;
    start = at;
  }
  if (start < quote.length) parts.push({ text: quote.slice(start), at: start, lit: false });
  return parts;
}
