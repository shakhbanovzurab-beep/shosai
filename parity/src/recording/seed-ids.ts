// Стабильные id и токены засева — общий файл с засевом на Python
// (recording/seed/ids.json). Визит открывает по ним известную запись; в фикстуре
// id всё равно заменяются заглушками, вместе с адресом визита.

import { readFileSync } from "node:fs";
import path from "node:path";

interface SeedIds {
  readonly meetings: Readonly<Record<string, string>>;
  readonly budgetSegment: string;
  readonly knowledgeDocument: string;
  readonly shares: Readonly<Record<string, string>>;
  readonly sharePassword: string;
}

export const SEED_IDS: SeedIds = JSON.parse(
  readFileSync(path.join(import.meta.dirname, "..", "..", "recording", "seed", "ids.json"), "utf8"),
) as SeedIds;

function known(table: Readonly<Record<string, string>>, key: string, what: string): string {
  const value = table[key];
  if (value === undefined) throw new Error(`В recording/seed/ids.json нет ${what} «${key}»`);
  return value;
}

/** Адрес встречи персоны «руководитель» по ключу засева. */
export function meetingUrl(key: string): string {
  return `/app/meetings/${known(SEED_IDS.meetings, key, "встречи")}`;
}

/** Адрес публичной страницы итога встречи по ключу ссылки. */
export function sharedUrl(key: string): string {
  return `/app/r/${known(SEED_IDS.shares, key, "ссылки")}`;
}
