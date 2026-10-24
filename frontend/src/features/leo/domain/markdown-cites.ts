import type { MdBlock, MdInline } from "./markdown";

/*
 * Номера источников внутри ответа (ADR 0068 AG-D1): `[n]` после утверждения. Маркер — только номер, который есть в
 * списке источников хода: выдуманный моделью номер остаётся текстом и не рисуется ссылкой.
 */

const MARKER = /\[(\d{1,2})\]/g;
// Знаки сразу после маркера: строка не переносится между ними и маркером, точка не остаётся одна на новой строке.
const TAIL = /^[.,;:!?…)\]»”’。、，；：！？）]+/u;

/** Кусок текста или номер источника; `key` — его место в тексте, `tail` — знаки препинания сразу после номера. */
export type CitedPart = { key: number; text: string } | { key: number; n: number; tail: string };

/** Текст, разрезанный на куски и номера источников, которые в нём упомянуты. */
export function citedParts(text: string, count: number): CitedPart[] {
  const parts: CitedPart[] = [];
  let start = 0;
  for (const match of text.matchAll(MARKER)) {
    const n = Number(match[1]);
    if (n < 1 || n > count) continue;
    const end = match.index + match[0].length;
    const tail = TAIL.exec(text.slice(end))?.[0] ?? "";
    if (match.index > start) parts.push({ key: start, text: text.slice(start, match.index) });
    parts.push({ key: match.index, n, tail });
    start = end + tail.length;
  }
  if (start < text.length) parts.push({ key: start, text: text.slice(start) });
  return parts;
}

function inlineCites(nodes: readonly MdInline[], count: number, found: Set<number>) {
  for (const node of nodes) {
    if (node.type === "text") {
      for (const part of citedParts(node.text, count)) if ("n" in part) found.add(part.n);
    }
    if ("children" in node) inlineCites(node.children, count, found);
  }
}

/** Номера источников, на которые опираются блоки: им подсвечивается то, что маркер подтверждает. */
export function citesIn(blocks: readonly MdBlock[], count: number, found = new Set<number>()): Set<number> {
  for (const block of blocks) {
    if (block.type === "paragraph" || block.type === "heading") inlineCites(block.children, count, found);
    else if (block.type === "quote") citesIn(block.blocks, count, found);
    else if (block.type === "list") for (const item of block.items) citesIn(item.blocks, count, found);
    else if (block.type === "table") {
      for (const cell of [...block.header, ...block.rows.flatMap((row) => row.cells)]) {
        inlineCites(cell.nodes, count, found);
      }
    }
  }
  return found;
}
