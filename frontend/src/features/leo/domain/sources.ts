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

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Отрывок, разбитый на части: `lit` — слова, подтверждающие ответ; `at` — начало части в отрывке, ключ для списка. */
export function quoteParts(quote: string, highlight: readonly string[]): QuotePart[] {
  const wanted = new Set(highlight.map((h) => h.toLowerCase()));
  const pieces =
    highlight.length === 0 ? [quote] : quote.split(new RegExp(`(${highlight.map(escapeRegExp).join("|")})`, "gi"));
  const parts: QuotePart[] = [];
  let at = 0;
  for (const text of pieces) {
    if (text) parts.push({ text, at, lit: wanted.has(text.toLowerCase()) });
    at += text.length;
  }
  return parts;
}
