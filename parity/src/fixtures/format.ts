// Формат фикстуры: запись одного визита на одном языке — всё, что фронтенд
// получил от /v1. Файл — fixtures/<визит>.<язык>.json.
//
// Фикстура самодостаточна: в ней сессия персоны и все обмены визита. Обмены
// отсортированы по ключу запроса, а повторы одного ключа идут в порядке
// возникновения. Так файл не зависит от того, в каком порядке параллельные
// запросы вернулись при записи, и две записи одного визита совпадают побайтно.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface Exchange {
  readonly method: string;
  readonly path: string;
  /** Строка запроса без «?», параметры отсортированы. */
  readonly query: string;
  readonly requestBody?: JsonValue;
  readonly status: number;
  readonly contentType: string;
  /** JSON — разобранным, текст — строкой, двоичные данные — base64 (см. bodyEncoding). */
  readonly body: JsonValue;
  readonly bodyEncoding?: "base64";
  /** recorded — ответ API черновика; synthetic — написан вручную, с причиной. */
  readonly origin: "recorded" | "synthetic";
  readonly reason?: string;
}

export interface Fixture {
  readonly visit: string;
  /** Язык записи: wh.lang и язык профиля персоны. */
  readonly language: string;
  /** null — анонимный визит. */
  readonly persona: string | null;
  readonly url: string;
  readonly draftCommit: string;
  readonly clock: string;
  /** Что лежит в localStorage до загрузки страницы: сессия, тема, язык. */
  readonly storage: Readonly<Record<string, string>>;
  readonly exchanges: readonly Exchange[];
}

export function exchangeKey(exchange: Pick<Exchange, "method" | "path" | "query">): string {
  return `${exchange.method} ${exchange.path}${exchange.query === "" ? "" : `?${exchange.query}`}`;
}

/** Строка запроса в каноническом виде: параметры отсортированы по имени и значению. */
export function canonicalQuery(search: URLSearchParams): string {
  const pairs = [...search.entries()].sort(([a, x], [b, y]) => (a === b ? x.localeCompare(y) : a.localeCompare(b)));
  return new URLSearchParams(pairs).toString();
}

/** Сортировка обменов по ключу; стабильная, поэтому повторы сохраняют порядок. */
export function sortExchanges(exchanges: readonly Exchange[]): Exchange[] {
  return [...exchanges].sort((a, b) => exchangeKey(a).localeCompare(exchangeKey(b)));
}

export function fixturePath(fixturesDir: string, visit: string, language: string): string {
  return path.join(fixturesDir, `${visit}.${language}.json`);
}

export function readFixture(fixturesDir: string, visit: string, language: string): Fixture {
  const file = fixturePath(fixturesDir, visit, language);
  if (!existsSync(file)) throw new Error(`Нет фикстуры ${visit} на языке ${language}: запишите визит (recording/record.sh)`);
  return JSON.parse(readFileSync(file, "utf8")) as Fixture;
}

export function writeFixture(fixturesDir: string, fixture: Fixture): string {
  const file = fixturePath(fixturesDir, fixture.visit, fixture.language);
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
  return file;
}
