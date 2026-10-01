// Конфигурация гармошки: закреплённый коммит черновика, момент и часовой пояс.
// Единственный источник — parity.config.json; скрипты оболочки читают тот же файл.

import { readFileSync } from "node:fs";
import path from "node:path";

export const PARITY_ROOT = path.resolve(import.meta.dirname, "..");

/** Origin, под которым браузер видит фронтенд. Резолва в DNS нет: все запросы
 *  к нему обслуживает перехват Playwright. */
export const ORIGIN = "http://parity.test";

export interface ParityConfig {
  readonly draftCommit: string;
  /** Момент гармошки: часы браузера и сервера черновика стоят на нём. */
  readonly clock: Date;
  readonly timezone: string;
  /** Каталог экспорта черновика на закреплённом коммите. */
  readonly draftExport: string;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`parity.config.json: поле ${field} должно быть непустой строкой`);
  }
  return value;
}

export function loadParityConfig(): ParityConfig {
  const raw: unknown = JSON.parse(readFileSync(path.join(PARITY_ROOT, "parity.config.json"), "utf8"));
  if (typeof raw !== "object" || raw === null) throw new Error("parity.config.json: ожидается объект");
  const record = raw as Record<string, unknown>;
  const draft = record["draft"] as Record<string, unknown> | undefined;
  const draftCommit = requireString(draft?.["commit"], "draft.commit");
  const clock = new Date(requireString(record["clock"], "clock"));
  if (Number.isNaN(clock.getTime())) throw new Error("parity.config.json: clock не является датой");
  return {
    draftCommit,
    clock,
    timezone: requireString(record["timezone"], "timezone"),
    draftExport: path.join(PARITY_ROOT, ".cache", "draft", draftCommit),
  };
}
