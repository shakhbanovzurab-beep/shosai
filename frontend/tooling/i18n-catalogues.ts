import type { Plugin } from "vite";

import { withFallback } from "../src/i18n/fallback";
import { NAMESPACES } from "../src/i18n/namespaces";
import { DEFAULT_LANGUAGE, LANGUAGE_CODES, type LanguageCode } from "../src/lib/language";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

type Tree = { [key: string]: string | Tree };

const VIRTUAL_ID = "virtual:i18n-catalogues";
const RESOLVED_ID = `\0${VIRTUAL_ID}`;
const FAILURE_ID = "virtual:i18n-failure-texts";
const RESOLVED_FAILURE_ID = `\0${FAILURE_ID}`;
const DEV_PREFIX = "/__i18n/";

// Читает все пространства имён одного языка; отсутствующий файл перевода — пустой объект.
function readLanguage(messagesDir: string, language: LanguageCode): Tree {
  const tree: Tree = {};
  for (const namespace of NAMESPACES) {
    const file = join(messagesDir, language, `${namespace}.json`);
    if (existsSync(file)) tree[namespace] = JSON.parse(readFileSync(file, "utf8")) as Tree;
    else if (language === DEFAULT_LANGUAGE) throw new Error(`Нет английского каталога ${file}`);
    else tree[namespace] = {};
  }
  return tree;
}

// Каталог языка поверх английского: пропуски перевода показываются по-английски, а не ключом.
function mergedTree(messagesDir: string, language: LanguageCode): Tree {
  const english = readLanguage(messagesDir, DEFAULT_LANGUAGE);
  return language === DEFAULT_LANGUAGE ? english : withFallback(english, readLanguage(messagesDir, language));
}

/** Каталог языка поверх английского как JSON: один файл со всеми пространствами имён. */
export const mergedCatalogue = (messagesDir: string, language: LanguageCode) =>
  JSON.stringify(mergedTree(messagesDir, language));

// Строка по пути ключей, или ошибка сборки, если такого сообщения нет.
function message(tree: Tree, path: readonly string[]): string {
  let node: string | Tree = tree;
  for (const key of path) {
    const next: string | Tree | undefined = typeof node === "string" ? undefined : node[key];
    if (next === undefined) throw new Error(`Нет сообщения ${path.join(".")}`);
    node = next;
  }
  if (typeof node !== "string") throw new Error(`${path.join(".")} — не сообщение`);
  return node;
}

// Тексты страницы сбоя на всех языках: их показывает корень, когда не загрузился даже каталог.
function failureTexts(messagesDir: string): string {
  const texts = Object.fromEntries(
    LANGUAGE_CODES.map((language) => {
      const tree = mergedTree(messagesDir, language);
      const [title, description, reload] = ["title", "description", "reload"].map((key) =>
        message(tree, ["pages", "error", key]),
      );
      return [language, { title, description, reload }];
    }),
  );
  return `export const failureTexts = ${JSON.stringify(texts)};\n`;
}

/**
 * Один файл сообщений на язык, с хешем содержимого в имени: браузер загружает только язык интерфейса
 * и кеширует его навсегда. Модуль `virtual:i18n-catalogues` отдаёт адреса файлов по кодам языков.
 */
export function i18nCatalogues(messagesDir: string): Plugin {
  let command: "build" | "serve" = "serve";
  const references = new Map<LanguageCode, string>();
  return {
    name: "whisperer:i18n-catalogues",
    configResolved(config) {
      command = config.command;
    },
    buildStart() {
      if (command !== "build") return;
      for (const language of LANGUAGE_CODES) {
        const source = mergedCatalogue(messagesDir, language);
        references.set(language, this.emitFile({ type: "asset", name: `messages-${language}.json`, source }));
      }
    },
    resolveId(id) {
      if (id === VIRTUAL_ID) return RESOLVED_ID;
      return id === FAILURE_ID ? RESOLVED_FAILURE_ID : undefined;
    },
    load(id) {
      if (id === RESOLVED_FAILURE_ID) return failureTexts(messagesDir);
      if (id !== RESOLVED_ID) return undefined;
      const entries = LANGUAGE_CODES.map((language) => {
        const url =
          command === "build"
            ? `import.meta.ROLLUP_FILE_URL_${references.get(language)}`
            : JSON.stringify(`${DEV_PREFIX}${language}.json`);
        return `  ${JSON.stringify(language)}: ${url},`;
      });
      return `export const catalogueUrls = {\n${entries.join("\n")}\n};\n`;
    },
    configureServer(server) {
      server.middlewares.use(DEV_PREFIX, (request, response, next) => {
        const language = request.url?.replace(/^\//, "").replace(/\.json$/, "");
        if (!language || !(LANGUAGE_CODES as readonly string[]).includes(language)) return next();
        response.setHeader("content-type", "application/json; charset=utf-8");
        response.end(mergedCatalogue(messagesDir, language as LanguageCode));
      });
    },
  };
}
