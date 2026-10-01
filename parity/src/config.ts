// Конфигурация стенда сравнения: закреплённый коммит черновика, пути сборки v2, момент и
// часовой пояс. Единственный источник — parity.config.json; скрипты оболочки
// читают тот же файл.

import { readFileSync } from "node:fs";
import path from "node:path";

export const PARITY_ROOT = path.resolve(import.meta.dirname, "..");
export const FIXTURES_DIR = path.join(PARITY_ROOT, "fixtures");

/** Origin, под которым браузер видит фронтенд. Резолва в DNS нет: все запросы
 *  к нему обслуживает перехват Playwright. Имя в зоне .localhost — защищённый
 *  контекст по стандарту, как HTTPS в бою: без него браузер прячет AudioWorklet
 *  голоса Leo, микрофон и push, и черновик рисует ошибки, которых в бою нет. */
export const ORIGIN = "http://parity.localhost";

export interface SitePaths {
  readonly appDir: string;
  readonly fontDirs: readonly string[];
  readonly rootDir: string;
}

export interface ParityConfig {
  readonly draftCommit: string;
  /** Момент стенда сравнения: часы браузера и сервера черновика стоят на нём. */
  readonly clock: Date;
  readonly timezone: string;
  /** Каталог экспорта черновика на закреплённом коммите. */
  readonly draftExport: string;
  /** Сборка фронтенда v2 и его статика — абсолютные пути. */
  readonly v2: SitePaths;
}

type RawRecord = Readonly<Record<string, unknown>>;

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`parity.config.json: поле ${field} должно быть непустой строкой`);
  }
  return value;
}

function requireRecord(value: unknown, field: string): RawRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`parity.config.json: поле ${field} должно быть объектом`);
  }
  return value as RawRecord;
}

function sitePaths(raw: RawRecord): SitePaths {
  const fontDirs = raw["fontDirs"];
  if (!Array.isArray(fontDirs)) throw new Error("parity.config.json: v2.fontDirs должно быть списком");
  const resolve = (value: unknown, field: string): string => path.resolve(PARITY_ROOT, requireString(value, field));
  return {
    appDir: resolve(raw["appDir"], "v2.appDir"),
    fontDirs: fontDirs.map((dir: unknown) => resolve(dir, "v2.fontDirs[]")),
    rootDir: resolve(raw["rootDir"], "v2.rootDir"),
  };
}

export function loadParityConfig(): ParityConfig {
  const record = requireRecord(JSON.parse(readFileSync(path.join(PARITY_ROOT, "parity.config.json"), "utf8")), "корень");
  const draftCommit = requireString(requireRecord(record["draft"], "draft")["commit"], "draft.commit");
  const clock = new Date(requireString(record["clock"], "clock"));
  if (Number.isNaN(clock.getTime())) throw new Error("parity.config.json: clock не является датой");
  return {
    draftCommit,
    clock,
    timezone: requireString(record["timezone"], "timezone"),
    draftExport: path.join(PARITY_ROOT, ".cache", "draft", draftCommit),
    v2: sitePaths(requireRecord(record["v2"], "v2")),
  };
}
