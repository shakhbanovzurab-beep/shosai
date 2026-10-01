// Генерация src/i18n/texts.json — тексты интерфейса, на которые ссылается стенд.
//
//   node scripts/extract-texts.ts
//
// Ключи — все вызовы `t("пространство:ключ")` в src/. Значения — из каталогов
// переводов экспорта черновика (scripts/export-draft.sh) на всех его языках.
// Пространство — это раздел (`features/<раздел>/locales/<язык>.json`) или общий
// каталог (`locales/<язык>/<имя>.json`), как у загрузчика черновика.
// Ключ, которого нет хоть в одном языке, — ошибка: маркер на этом языке не сработал бы.

import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { loadParityConfig } from "../src/config.ts";
import { TEXT_KEY_PATTERN, TEXTS_FILE } from "../src/i18n/texts.ts";

type Catalog = { readonly [key: string]: unknown };

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    // Тесты стенда ключами интерфейса не пользуются; в них — проверочные ключи.
    return entry.name.endsWith(".ts") && !entry.name.endsWith(".test.ts") ? [full] : [];
  });
}

function usedKeys(srcDir: string): string[] {
  const keys = new Set<string>();
  for (const file of sourceFiles(srcDir)) {
    for (const match of readFileSync(file, "utf8").matchAll(TEXT_KEY_PATTERN)) {
      const key = match[1];
      if (key !== undefined) keys.add(key);
    }
  }
  return [...keys].sort();
}

function catalogFile(frontendSrc: string, namespace: string, language: string): string {
  const feature = path.join(frontendSrc, "features", namespace, "locales", `${language}.json`);
  return existsSync(feature) ? feature : path.join(frontendSrc, "locales", language, `${namespace}.json`);
}

/** Значение по пути ключа; читаются только собственные свойства каталога. */
function lookup(catalog: Catalog, dottedPath: string): string | undefined {
  let node: unknown = catalog;
  for (const part of dottedPath.split(".")) {
    if (typeof node !== "object" || node === null || !Object.hasOwn(node, part)) return undefined;
    node = Object.getOwnPropertyDescriptor(node, part)?.value;
  }
  return typeof node === "string" ? node : undefined;
}

function main(): void {
  const config = loadParityConfig();
  const frontendSrc = path.join(config.draftExport, "frontend", "src");
  if (!existsSync(frontendSrc)) throw new Error(`Нет экспорта черновика: ${frontendSrc} (scripts/export-draft.sh)`);
  const languages = readdirSync(path.join(frontendSrc, "locales")).sort();
  const keys = usedKeys(path.resolve(import.meta.dirname, "..", "src"));
  const cache = new Map<string, Catalog>();
  const missing: string[] = [];
  const result: Record<string, Record<string, string>> = {};
  for (const language of languages) {
    const texts: Record<string, string> = {};
    for (const key of keys) {
      const [namespace = "", dottedPath = ""] = key.split(":");
      const file = catalogFile(frontendSrc, namespace, language);
      if (!cache.has(file)) cache.set(file, existsSync(file) ? (JSON.parse(readFileSync(file, "utf8")) as Catalog) : {});
      const value = lookup(cache.get(file) ?? {}, dottedPath);
      if (value === undefined) missing.push(`${language} ${key}`);
      else texts[key] = value;
    }
    result[language] = texts;
  }
  if (missing.length > 0) throw new Error(`Ключей нет в каталогах черновика:\n${missing.join("\n")}`);
  writeFileSync(TEXTS_FILE, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  console.info(`texts.json: ${keys.length} ключей × ${languages.length} языков`);
}

main();
