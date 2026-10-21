/*
 * Комментарий — простой текст; ссылки в нём становятся кликабельными. Знаки препинания в конце не входят в
 * ссылку: «см. https://example.com.» ведёт на example.com.
 */

/** Кусок текста: `start` — его место в тексте, годится в ключ. */
export type TextPart = { text: string; href: string | null; start: number };

const URL_PATTERN = /https?:\/\/[^\s<>"']+/g;
const TRAILING = /[.,;:!?)\]}»”’]+$/;

export function linkParts(text: string): TextPart[] {
  const parts: TextPart[] = [];
  let last = 0;
  for (const match of text.matchAll(URL_PATTERN)) {
    const start = match.index;
    const href = match[0].replace(TRAILING, "");
    if (start > last) parts.push({ text: text.slice(last, start), href: null, start: last });
    parts.push({ text: href, href, start });
    last = start + href.length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), href: null, start: last });
  return parts;
}
