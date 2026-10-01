// Стабильные id и токены засева — общий файл с засевом на Python
// (recording/seed/ids.json). Визит открывает по ним известную запись; в фикстуре
// id всё равно заменяются заглушками, вместе с адресом визита.

import { readFileSync } from "node:fs";
import path from "node:path";

import { ORIGIN } from "../config.ts";

interface SeedIds {
  readonly meetings: Readonly<Record<string, string>>;
  readonly budgetSegment: string;
  readonly knowledgeDocument: string;
  readonly shares: Readonly<Record<string, string>>;
  readonly sharePassword: string;
  readonly hubs: Readonly<Record<string, string>>;
  readonly rooms: Readonly<Record<string, string>>;
  readonly streams: Readonly<Record<string, string>>;
  readonly roomInvite: string;
  readonly roomInvites: Readonly<Record<string, string>>;
  readonly fileShares: Readonly<Record<string, string>>;
  readonly streamInvites: Readonly<Record<string, string>>;
  readonly knocks: Readonly<Record<string, string>>;
  readonly boards: Readonly<Record<string, string>>;
  readonly streamInvite: string;
  readonly prompts: Readonly<Record<string, string>>;
  readonly mcp: {
    readonly clientId: string;
    readonly redirectUri: string;
    readonly scopes: readonly string[];
    readonly codeChallenge: string;
    readonly state: string;
  };
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

/** Адрес дела «руководителя» по ключу засева. */
export function hubUrl(key: string): string {
  return `/app/hub/${known(SEED_IDS.hubs, key, "дела")}`;
}

/** Адрес редактора промпта «руководителя» по ключу засева. */
export function promptUrl(key: string): string {
  return `/app/prompts/${known(SEED_IDS.prompts, key, "промпта")}`;
}

/**
 * Экран согласия OAuth для зарегистрированного клиента «Claude»: так его
 * открывает внешний AI. Вызов кода — пример RFC 7636; ресурс — сервер MCP стенда.
 */
export function mcpConsentUrl(): string {
  const { clientId, redirectUri, scopes, codeChallenge, state } = SEED_IDS.mcp;
  const query = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
    scope: scopes.join(" "),
    state,
    resource: `${ORIGIN}/mcp`,
  });
  return `/app/connect/mcp?${query.toString()}`;
}

/** Адрес входа хоста в комнату «руководителя» по ключу засева. */
export function roomUrl(key: string): string {
  return `/app/rooms/${known(SEED_IDS.rooms, key, "комнаты")}`;
}

/** Адрес студии трансляции «руководителя» по ключу засева. */
export function studioUrl(key: string): string {
  return `/app/studio/${known(SEED_IDS.streams, key, "трансляции")}`;
}

/** Адрес доски трекера «руководителя» по коду проекта. */
export function boardUrl(key: string): string {
  return `/app/tracker/${known(SEED_IDS.boards, key, "доски")}`;
}
