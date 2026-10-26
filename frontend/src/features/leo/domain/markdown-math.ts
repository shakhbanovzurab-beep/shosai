import type { TokenizerExtension, Tokens } from "marked";

/*
 * Формулы TeX в ответе Leo: блоком — `$$…$$` и `\[…\]` с начала строки, в строке — `\(…\)`, `$$…$$` и `$…$`.
 * Цена — не формула: у `$…$` за открывающим знаком не пробел, перед закрывающим не пробел, а за ним не цифра,
 * поэтому «$15 за место» и «от $5 до $10» остаются текстом. Незакрытая формула посреди потока читается как текст.
 */

export type MathToken = Tokens.Generic & { type: "blockMath" | "inlineMath"; text: string; display: boolean };

const BLOCK = /^ {0,3}(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]) *(?:\n+|$)/;
const BLOCK_START = /(?:^|\n) {0,3}(?:\$\$|\\\[)/;
const INLINE_PAREN = /^\\\(([\s\S]+?)\\\)/;
const INLINE_DISPLAY = /^\$\$((?:\\.|[^\\$])+?)\$\$/;
const INLINE_DOLLAR = /^\$(?![\s$])((?:\\.|[^\\$\n])+?)(?<![\s\\])\$(?!\d)/;
const INLINE_START = /\$|\\\(/;

function blockStart(src: string): number | undefined {
  const match = BLOCK_START.exec(src);
  if (match === null) return undefined;
  return match[0].startsWith("\n") ? match.index + 1 : match.index;
}

const mathToken = (type: MathToken["type"], raw: string, text: string, display: boolean): MathToken => ({
  type,
  raw,
  text: text.trim(),
  display,
});

export const blockMath: TokenizerExtension = {
  name: "blockMath",
  level: "block",
  start: blockStart,
  tokenizer(src) {
    const match = BLOCK.exec(src);
    if (match === null) return undefined;
    return mathToken("blockMath", match[0], match[1] ?? match[2] ?? "", true);
  },
};

export const inlineMath: TokenizerExtension = {
  name: "inlineMath",
  level: "inline",
  start(src) {
    const at = src.search(INLINE_START);
    return at < 0 ? undefined : at;
  },
  tokenizer(src) {
    const paren = INLINE_PAREN.exec(src);
    if (paren !== null) return mathToken("inlineMath", paren[0], paren[1], false);
    const display = INLINE_DISPLAY.exec(src);
    if (display !== null) return mathToken("inlineMath", display[0], display[1], true);
    const dollar = INLINE_DOLLAR.exec(src);
    return dollar === null ? undefined : mathToken("inlineMath", dollar[0], dollar[1], false);
  },
};

/** Языки забора, чей блок — формула: модели пишут формулы и так. */
export const MATH_LANGUAGES = new Set(["math", "latex", "tex", "katex"]);
