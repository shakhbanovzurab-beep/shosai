import { Marked, type MarkedToken, type Token, type Tokens } from "marked";

import { blockMath, inlineMath, MATH_LANGUAGES, type MathToken } from "./markdown-math";

/*
 * Ответ модели в Markdown — как безопасное дерево (ADR 0068 AG-D6). Лексер — `marked`; разметку строит кабинет:
 * сырой HTML модели остаётся текстом, ссылка — только `https`, `http`, `mailto` или путь кабинета, картинка — только
 * её подпись: ничего внешнего не загружается. Незаконченная разметка посреди потока читается как текст.
 */

// `key` — место узла среди соседей в тексте, который только дописывается: тот же узел — тот же ключ всё время потока.
export type MdInline = { key: string } & (
  | { type: "text"; text: string }
  | { type: "strong" | "em" | "del"; children: MdInline[] }
  | { type: "code"; text: string }
  | { type: "link"; href: string; children: MdInline[] }
  | { type: "math"; tex: string; display: boolean }
  | { type: "br" }
);

export type MdAlign = "left" | "center" | "right" | null;
export type MdCell = { key: string; nodes: MdInline[] };
export type MdItem = { key: string; blocks: MdBlock[] };

export type MdBlock = { key: string } & (
  | { type: "paragraph"; children: MdInline[] }
  | { type: "heading"; depth: number; children: MdInline[] }
  /** `closed` — забор блока закрыт: код дописан, и его можно рисовать целиком (диаграмма, формула). */
  | { type: "code"; lang: string; text: string; closed: boolean }
  | { type: "quote"; blocks: MdBlock[] }
  | { type: "list"; ordered: boolean; start: number; items: MdItem[] }
  | { type: "table"; align: MdAlign[]; header: MdCell[]; rows: { key: string; cells: MdCell[] }[] }
  | { type: "math"; tex: string }
  | { type: "rule" }
);

// Узел без ключа: ключи раздаёт `keyed` по месту среди соседей.
type Unkeyed<T> = T extends unknown ? Omit<T, "key"> : never;

/** Узлы с ключами по их месту: текст только дописывается, поэтому место — стабильная идентичность узла. */
function keyed<T>(nodes: Unkeyed<T>[]): T[] {
  return nodes.map((node, at) => ({ ...node, key: String(at) }) as T);
}

const SAFE_SCHEME = /^(https?:|mailto:)/i;
const ENTITY = /&(amp|lt|gt|quot|#39|apos|#\d{1,6}|#x[\da-f]{1,6});/gi;
const NAMED: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", apos: "'" };

/** Адрес, по которому ссылка может вести: веб, почта или страница кабинета; иначе null. */
export function safeHref(href: string): string | null {
  const trimmed = href.trim();
  if (SAFE_SCHEME.test(trimmed)) return trimmed;
  // Путь кабинета — от корня, но не протокол-относительный адрес чужого сайта (`//evil.example`).
  if (trimmed.startsWith("/") && !trimmed.startsWith("//") && !trimmed.startsWith("/\\")) return trimmed;
  return null;
}

/** Текст с раскрытыми сущностями HTML: разметку экранирует React, а `&amp;` модели читается как «&». */
export function decoded(text: string): string {
  return text.replace(ENTITY, (whole, name: string) => {
    const key = name.toLowerCase();
    if (key in NAMED) return NAMED[key];
    const code = key.startsWith("#x") ? Number.parseInt(key.slice(2), 16) : Number.parseInt(key.slice(1), 10);
    return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : whole;
  });
}

function inlineOf(tokens: readonly Token[] | undefined): MdInline[] {
  return keyed<MdInline>((tokens ?? []).flatMap((token) => inlineNode(token)));
}

function inlineNode(token: Token): Unkeyed<MdInline>[] {
  if (token.type === "inlineMath") {
    const math = token as MathToken;
    return [{ type: "math", tex: math.text, display: math.display }];
  }
  {
    const t = token as MarkedToken;
    switch (t.type) {
      case "strong":
      case "em":
      case "del":
        return [{ type: t.type, children: inlineOf(t.tokens) }];
      case "codespan":
        return [{ type: "code", text: decoded(t.text) }];
      case "br":
        return [{ type: "br" }];
      case "link": {
        const href = safeHref(t.href);
        return href === null
          ? t.tokens.flatMap((child) => inlineNode(child))
          : [{ type: "link", href, children: inlineOf(t.tokens) }];
      }
      case "image":
        return t.text ? [{ type: "text", text: decoded(t.text) }] : [];
      case "text":
        return "tokens" in t && t.tokens
          ? t.tokens.flatMap((child) => inlineNode(child))
          : [{ type: "text", text: decoded(t.text) }];
      case "escape":
      case "html":
        return [{ type: "text", text: t.type === "html" ? t.text : decoded(t.text) }];
      default:
        return "raw" in token ? [{ type: "text", text: token.raw }] : [];
    }
  }
}

const FENCE_OPEN = /^ {0,3}(`{3,}|~{3,})/;

/** Блок кода дописан: у блока с забором есть закрывающий забор не короче открывающего; блок отступом — всегда. */
export function fenceClosed(raw: string): boolean {
  const open = FENCE_OPEN.exec(raw)?.[1];
  if (open === undefined) return true;
  const lines = raw.trimEnd().split("\n");
  if (lines.length < 2) return false;
  const last = lines.at(-1)?.trim() ?? "";
  return last.length >= open.length && [...last].every((char) => char === open[0]);
}

// Пункт «тесного» списка — строка текста, а не абзац: она тоже становится абзацем пункта.
const listItemOf = (item: Tokens.ListItem): Unkeyed<MdItem> => ({ blocks: blocksOf(item.tokens) });
const cellOf = (cell: Tokens.TableCell): Unkeyed<MdCell> => ({ nodes: inlineOf(cell.tokens) });

function blockOf(token: Token): Unkeyed<MdBlock>[] {
  if (token.type === "blockMath") return [{ type: "math", tex: (token as MathToken).text }];
  const t = token as MarkedToken;
  switch (t.type) {
    case "paragraph":
      return [{ type: "paragraph", children: inlineOf(t.tokens) }];
    case "text":
      return [{ type: "paragraph", children: inlineOf(t.tokens ?? [{ type: "text", raw: t.text, text: t.text }]) }];
    case "heading":
      return [{ type: "heading", depth: t.depth, children: inlineOf(t.tokens) }];
    case "code": {
      const lang = (t.lang ?? "").split(/\s/)[0];
      const closed = fenceClosed(t.raw);
      // Формула в заборе рисуется, когда он закрыт; до того — кодом, как пишется.
      if (closed && MATH_LANGUAGES.has(lang.toLowerCase())) return [{ type: "math", tex: t.text.trim() }];
      return [{ type: "code", lang, text: t.text, closed }];
    }
    case "blockquote":
      return [{ type: "quote", blocks: blocksOf(t.tokens) }];
    case "list":
      return [
        {
          type: "list",
          ordered: t.ordered,
          start: Number(t.start) || 1,
          items: keyed<MdItem>(t.items.map(listItemOf)),
        },
      ];
    case "table":
      return [
        {
          type: "table",
          align: t.align,
          header: keyed<MdCell>(t.header.map(cellOf)),
          rows: keyed<{ key: string; cells: MdCell[] }>(
            t.rows.map((row) => ({ cells: keyed<MdCell>(row.map(cellOf)) })),
          ),
        },
      ];
    case "hr":
      return [{ type: "rule" }];
    case "html":
      return t.text.trim() ? [{ type: "paragraph", children: [{ key: "0", type: "text", text: t.text.trim() }] }] : [];
    default:
      return [];
  }
}

/** Блоки из токенов лексера; пробелы между блоками и определения ссылок не рисуются. */
export function blocksOf(tokens: readonly Token[]): MdBlock[] {
  return keyed<MdBlock>(tokens.flatMap(blockOf));
}

// Свой экземпляр лексера: расширения формул не меняют общий `marked` других мест кабинета.
const lexer = new Marked({ gfm: true, breaks: true, extensions: [blockMath, inlineMath] });

/** Токены верхнего уровня текста: блок за блоком, с их исходным текстом. */
export function lexed(text: string): Token[] {
  return lexer.lexer(text);
}
