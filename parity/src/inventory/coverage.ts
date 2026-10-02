// Сверка инвентаризации с реестром состояний — правило плана D2: каждое
// состояние из таблиц parity/inventory/*.md снято, видно на другом снимке или
// исключено с причиной (раздел «Coverage in the screenshot matrix» группы).
//
// Первая колонка таблицы называет одно или несколько состояний: полный id и
// варианты к нему — `a.b.c` / `.d` / `e`. Вариант без точки в начале и с точкой
// в начале одинаково относительны: запись в документах не говорит, заменяет
// вариант последние сегменты или дописывается к id (`a.b` / `.error` — это
// `a.b.error`), поэтому годится любой префикс полного id, включая его самого.

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

/** Состояние, названное в таблице: подходит любой из вариантов прочтения. */
export interface StateRef {
  readonly text: string;
  readonly candidates: readonly string[];
}

export interface InventoryGroup {
  readonly file: string;
  /** Состояния из таблиц инвентаризации. */
  readonly inventoried: readonly StateRef[];
  /** Состояния из таблиц раздела покрытия: на другом снимке или не снимаются. */
  readonly covered: readonly StateRef[];
}

const COVERAGE_HEADING = /^### Coverage in the screenshot matrix/m;
const END_OF_INVENTORY = /^### (Findings|Coverage)/m;
const TOKEN = /^\.?[a-z0-9*][a-z0-9.*-]*$/;

/** Токены первой ячейки: id в обратных кавычках, а без кавычек — слова между разделителями. */
function cellTokens(cell: string): string[] {
  const text = cell.replace(/\([^)]*\)/g, " ");
  const quoted = [...text.matchAll(/`([^`]+)`/g)].map((match) => match[1] ?? "");
  const words = quoted.length > 0 ? quoted : text.split(/\s*(?:\/|,|;|\+)\s*/);
  return words
    .map((word) => (word.trim().split(/\s+/)[0] ?? "").replace(/-?<[^>]+>|-N\b/g, "-*"))
    .filter((word) => TOKEN.test(word));
}

/** Состояния первой ячейки строки таблицы; относительный вариант — от последнего полного id. */
export function cellStateRefs(cell: string): StateRef[] {
  const refs: StateRef[] = [];
  let anchor: readonly string[] | null = null;
  for (const token of cellTokens(cell)) {
    if (!token.startsWith(".") && token.includes(".")) {
      refs.push({ text: token, candidates: [token] });
      anchor = token.split(".");
      continue;
    }
    if (anchor === null) continue;
    const variant = token.replace(/^\./, "");
    const candidates: string[] = [];
    for (let length = anchor.length - 1; length >= 1; length--) candidates.push([...anchor.slice(0, length), variant].join("."));
    candidates.push([...anchor, variant].join("."));
    refs.push({ text: token, candidates });
  }
  return refs;
}

function tableRefs(markdown: string): StateRef[] {
  return markdown
    .split("\n")
    .filter((line) => line.startsWith("|") && !line.startsWith("|---"))
    .flatMap((line) => cellStateRefs(line.split("|")[1] ?? ""));
}

export function parseInventoryGroup(file: string, markdown: string): InventoryGroup {
  const end = markdown.search(END_OF_INVENTORY);
  const coverageStart = markdown.search(COVERAGE_HEADING);
  return {
    file,
    inventoried: tableRefs(end === -1 ? markdown : markdown.slice(0, end)),
    covered: coverageStart === -1 ? [] : tableRefs(markdown.slice(coverageStart)),
  };
}

export function readInventoryGroups(inventoryDir: string): InventoryGroup[] {
  return readdirSync(inventoryDir)
    .filter((file) => file.endsWith(".md") && file !== "README.md")
    .sort()
    .map((file) => parseInventoryGroup(file, readFileSync(path.join(inventoryDir, file), "utf8")));
}

/** Совпадение со строкой, где `*` — любой фрагмент: части между звёздочками идут по порядку. */
function matchesParts(pattern: string, value: string): boolean {
  const parts = pattern.split("*");
  if (parts.length === 1) return pattern === value;
  const first = parts[0] ?? "";
  const last = parts.at(-1) ?? "";
  if (value.length < first.length + last.length || !value.startsWith(first) || !value.endsWith(last)) return false;
  let position = first.length;
  for (const part of parts.slice(1, -1)) {
    const found = value.indexOf(part, position);
    if (found === -1 || found + part.length > value.length - last.length) return false;
    position = found + part.length;
  }
  return true;
}

/**
 * Шаблон id: `*` — любой фрагмент; хвост `.*` или `-*` — продолжение через точку
 * или дефис либо ничего (`year-*` ↔ `year`, `expanded.*` ↔ `expanded-loading`).
 */
export function matchesPattern(pattern: string, value: string): boolean {
  if (!pattern.endsWith(".*") && !pattern.endsWith("-*")) return matchesParts(pattern, value);
  const base = pattern.slice(0, -2);
  return matchesParts(base, value) || matchesParts(`${base}.*`, value) || matchesParts(`${base}-*`, value);
}

/** Снято: тот же id, его подсостояние (`a.b` → `a.b.c`, `a.b-c`) или подходящий шаблон. */
function captured(candidate: string, registered: readonly string[]): boolean {
  if (candidate.includes("*")) return registered.some((id) => matchesPattern(candidate, id));
  return registered.some((id) => id === candidate || id.startsWith(`${candidate}.`) || id.startsWith(`${candidate}-`));
}

/**
 * Шаблон покрытия закрывает состояния, только если до `*` стоят хотя бы два
 * сегмента: строка «en cells of `livekit.*`» говорит о языке, а не о состояниях.
 */
function specificPattern(entry: string): boolean {
  return entry.split(".").findIndex((segment) => segment.includes("*")) >= 2;
}

function explained(candidate: string, covered: readonly StateRef[]): boolean {
  return covered.some((ref) =>
    ref.candidates.some((entry) => entry === candidate || (entry.includes("*") && specificPattern(entry) && matchesPattern(entry, candidate))),
  );
}

/** Состояния инвентаризации без снимка и без строки в разделе покрытия своей группы. */
export function inventoryGaps(groups: readonly InventoryGroup[], registered: readonly string[]): string[] {
  const gaps: string[] = [];
  for (const group of groups) {
    for (const ref of group.inventoried) {
      if (ref.candidates.some((candidate) => captured(candidate, registered) || explained(candidate, group.covered))) continue;
      gaps.push(`${group.file}: ${ref.candidates[0] ?? ref.text}`);
    }
  }
  return gaps;
}
