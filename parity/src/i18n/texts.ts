// Тексты интерфейса для маркеров и действий — из каталогов переводов черновика.
//
// Маркер «экран открылся» и кнопка, которую нажимает визит, задаются ключом
// перевода, а не русской строкой: один и тот же визит работает на любом из 16
// языков. Тексты берутся у черновика, потому что v2 обязан показывать ровно их.
//
// Каталоги черновика весят мегабайты и в CI недоступны, поэтому используемые
// ключи лежат в texts.json — его пишет scripts/extract-texts.ts из экспорта
// черновика на закреплённом коммите.

import { readFileSync } from "node:fs";
import path from "node:path";

/** Текст по ключу `пространство:путь.ключа` с подстановкой {{переменных}}. */
export type Translate = (key: string, values?: Readonly<Record<string, string | number>>) => string;

type TextCatalog = Readonly<Record<string, Readonly<Record<string, string>>>>;

export const TEXTS_FILE = path.join(import.meta.dirname, "texts.json");

/** Ключи в коде стенда: `t("auth:titleLogin")`. Тот же образец ищет генератор. */
export const TEXT_KEY_PATTERN = /\bt\(\s*"([\w-]+:[\w.-]+)"/g;

function loadCatalog(): TextCatalog {
  return JSON.parse(readFileSync(TEXTS_FILE, "utf8")) as TextCatalog;
}

function interpolate(template: string, values: Readonly<Record<string, string | number>>): string {
  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, name: string) => {
    const value = values[name];
    if (value === undefined) throw new Error(`Нет значения {{${name}}} для текста «${template}»`);
    return String(value);
  });
}

export function translator(language: string, catalog: TextCatalog = loadCatalog()): Translate {
  const texts = catalog[language];
  if (texts === undefined) throw new Error(`В texts.json нет языка ${language}`);
  return (key, values = {}) => {
    const template = texts[key];
    if (template === undefined) {
      throw new Error(`Ключа ${key} нет в texts.json для ${language}: запустите scripts/extract-texts.ts`);
    }
    return interpolate(template, values);
  };
}

/** Селектор «элемент с текстом»: кавычки в тексте экранируются JSON-строкой. */
export function withText(selector: string, text: string): string {
  return `${selector}:has-text(${JSON.stringify(text)})`;
}

/**
 * Элемент, текст которого содержит строку (без учёта регистра). Для текстов с
 * подстановкой, которую форматирует сам фронтенд (размер, дата): маркер — их начало.
 */
export function containsText(text: string): string {
  return `text=${text.trim()}`;
}

/** Элемент, весь текст которого равен строке (видимость проверяется у него самого). */
export function exactText(text: string): string {
  return `text=${JSON.stringify(text)}`;
}
