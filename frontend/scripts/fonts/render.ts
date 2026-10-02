// Таблицы стилей шрифтов из каталога (спека 084 черновика): правила «язык × роль»
// для документа и файлы `@font-face` по паре «язык × роль». Чистые функции:
// запись на диск и сверка — в generate.ts, проверка в тестах — тот же вызов.

import { LOCALES } from "../../src/core/i18n/locales.ts";
import {
  DEFAULT_FONT_ROLE,
  FONT_CONFIG,
  FONT_LOCALES,
  FONT_ROLES,
  type FontLocale,
  type FontRole,
} from "../../src/core/theme/fontCatalogue.ts";

/** Запись манифеста `fonts/faces.json`: один файл woff2 одного семейства. */
export interface FontFaceEntry {
  readonly family: string;
  readonly file: string;
  readonly range: string;
  readonly style: string;
  /** Вес или диапазон весов вариативного файла: `400` либо `"400 900"`. */
  readonly weight: number | string;
}

/** Правила «язык × роль → семейства»; путь от каталога `frontend/`. */
export const ROLE_RULES_PATH = "src/core/styles/generated/font-roles.css";

/** Файл объявлений `@font-face` пары «язык × роль»; раздаётся как `/fonts/<имя>`. */
export function faceSheetPath(lang: string, role: FontRole): string {
  return `fonts/roles-${lang}-${role}.css`;
}

/** Значение `<html lang>` для языка каталога: у китайского это `zh-Hant`. */
export function hreflangOf(locale: FontLocale): string {
  const entry = LOCALES.find((candidate) => candidate.code === locale);
  if (entry === undefined) throw new Error(`Языка ${locale} нет в реестре локалей`);
  return entry.hreflang;
}

/**
 * Правила документа. Фирменная роль не ставит `data-font` и адресуется одним
 * `lang` (специфичность 0,1,1); остальные роли — парой атрибутов (0,2,1), поэтому
 * роль бьёт язык при любом порядке правил. Парное правило `.wh-swatch` — для
 * плитки выбора, которая живёт внутри документа и иначе унаследовала бы его шрифт.
 * Заголовки фирменной роли набраны Unbounded на всех языках: у каждого
 * `@font-face` свой `unicode-range`, и чужие письменности берёт следующее лицо.
 */
function renderRoleRules(): string {
  const lines = [
    "/* @generated scripts/fonts/generate.ts из src/core/theme/fontCatalogue.ts.",
    "   Правки затрутся: меняйте каталог, а не этот файл. */",
    "",
  ];
  for (const locale of FONT_LOCALES) {
    const lang = hreflangOf(locale);
    const set = FONT_CONFIG[locale];
    lines.push(
      `html[lang="${lang}"],`,
      `html[lang="${lang}"] .wh-swatch[data-font="${DEFAULT_FONT_ROLE}"] {`,
      `  --ui-sans: ${set[DEFAULT_FONT_ROLE].stack};`,
      `  --ui-head: "Unbounded", ${set[DEFAULT_FONT_ROLE].stack};`,
      "}",
    );
    for (const role of FONT_ROLES) {
      if (role === DEFAULT_FONT_ROLE) continue;
      lines.push(
        `html[lang="${lang}"][data-font="${role}"],`,
        `html[lang="${lang}"] .wh-swatch[data-font="${role}"] {`,
        `  --ui-sans: ${set[role].stack};`,
        `  --ui-head: ${set[role].stack};`,
        "}",
      );
    }
    lines.push("");
  }
  return `${lines.join("\n").replace(/\n{3,}/g, "\n\n").trimEnd()}\n`;
}

const weightBounds = (weight: number | string): readonly [number, number] => {
  const parts = String(weight).split(" ").map(Number);
  return [parts[0] ?? Number.NaN, parts.at(-1) ?? Number.NaN];
};

/**
 * Объявления семейства. Один файл вариативного шрифта манифест перечисляет по
 * разу на вес; такие записи схлопываются в диапазон `font-weight: 400 700`.
 * У статических семейств на каждый вес свой файл, и диапазон не объявляется.
 */
function renderFamily(entries: readonly FontFaceEntry[]): string[] {
  const byFile = Map.groupBy(entries, (entry) => `${entry.file}|${entry.style}`);
  return [...byFile.values()].map((group) => {
    const bounds = group.map((entry) => weightBounds(entry.weight));
    const low = Math.min(...bounds.map(([from]) => from));
    const high = Math.max(...bounds.map(([, to]) => to));
    const [first] = group as [FontFaceEntry, ...FontFaceEntry[]];
    const weight = low === high ? `${low}` : `${low} ${high}`;
    return (
      "@font-face{" +
      `font-family:'${first.family}';font-style:${first.style};font-weight:${weight};` +
      `font-display:swap;src:url('/fonts/${first.file}') format('woff2');` +
      `unicode-range:${first.range};}`
    );
  });
}

/**
 * Все сгенерированные файлы: путь от `frontend/` → содержимое. Объявления
 * разложены по паре «язык × роль»: все вместе — 3 МБ текста, а до первого кадра
 * нужна одна пара.
 */
export function renderFontStylesheets(faces: readonly FontFaceEntry[]): Map<string, string> {
  const families = Map.groupBy(faces, (entry) => entry.family);
  const files = new Map([[ROLE_RULES_PATH, renderRoleRules()]]);
  for (const locale of FONT_LOCALES) {
    for (const role of FONT_ROLES) {
      const lines = ["/* @generated scripts/fonts/generate.ts — правки затрутся. */"];
      for (const family of FONT_CONFIG[locale][role].hosted.toSorted()) {
        const entries = families.get(family);
        if (entries === undefined) throw new Error(`Семейства «${family}» нет в fonts/faces.json`);
        lines.push(...renderFamily(entries));
      }
      files.set(faceSheetPath(hreflangOf(locale), role), `${lines.join("\n")}\n`);
    }
  }
  return files;
}

/** Пути, у которых файл на диске отсутствует или расходится с отрисованным. */
export function findDrift(
  files: ReadonlyMap<string, string>,
  readExisting: (path: string) => string | null,
): string[] {
  return [...files].filter(([path, text]) => readExisting(path) !== text).map(([path]) => path);
}

const isFaceEntry = (value: unknown): value is FontFaceEntry => {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Record<string, unknown>;
  return (
    ["family", "file", "range", "style"].every((key) => typeof entry[key] === "string") &&
    (typeof entry["weight"] === "number" || typeof entry["weight"] === "string")
  );
};

/** Разбирает манифест; любая запись неверной формы — ошибка, а не пропуск. */
export function parseFaces(raw: unknown): FontFaceEntry[] {
  if (!Array.isArray(raw)) throw new Error("fonts/faces.json: ожидается список записей");
  const invalid = raw.findIndex((entry) => !isFaceEntry(entry));
  if (invalid !== -1) throw new Error(`fonts/faces.json: запись ${invalid} неверной формы`);
  return raw as FontFaceEntry[];
}
