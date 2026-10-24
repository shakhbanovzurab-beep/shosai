/*
 * Источники ответа Leo: «каждый ответ называет свои источники и пространство, откуда каждый» (ADR 0039 §7,
 * ADR 0068 AG-D1): событие `sources` в потоке и маркеры `[n]` в тексте ответа; номера дают инструменты.
 */

export type SourceKind = "meeting" | "file" | "task" | "note" | "mail" | "web";

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
