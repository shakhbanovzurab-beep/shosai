// Командное меню (шаг 3b): короткий запрос, поиск, пустая выдача, молчащая база
// знаний. Выдача с находками снимается с разделом поиска — на записанных данных.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../i18n/texts.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const SEARCH = "/v1/me/search";
/** Два символа, не совпадающие ни с одной командой: меню идёт в поиск. */
const QUERY = "zz";

const palette = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("common:palette.title"))}]`;

async function typeQuery(page: Page, { t }: StateContext, query: string): Promise<void> {
  await page.locator("[data-onboarding='sidebar-search']").click();
  await page.locator(`${palette(t)} input`).fill(query);
}

/** Пустая выдача поиска; `unavailable` — домены, которые не ответили. */
function nothingFound(unavailable: readonly string[], reason: string): ReturnType<typeof reply> {
  return reply("GET", SEARCH, 200, { query: QUERY, total: 0, hits: [], unavailable: [...unavailable] }, reason);
}

function paletteState(id: string, query: string, overrides: State["overrides"], marker: (t: Translate) => string): State {
  return {
    id: `shell.palette.${id}`,
    fixture: "shell/home-free",
    scope: "single",
    ...(overrides === undefined ? {} : { overrides }),
    act: async (page, context) => typeQuery(page, context, query),
    marker: (t) => `${palette(t)} >> ${marker(t)}`,
  };
}

export const PALETTE_STATES: readonly State[] = [
  {
    // Находки по данным «руководителя»: встречи, календарь, контекст, документы.
    id: "shell.palette.results",
    fixture: "meetings/search",
    scope: "single",
    act: async (page, context) => typeQuery(page, context, "бюджет"),
    marker: (t) => `${palette(t)} >> text="Планирование бюджета Q4"`,
  },
  paletteState("too-short", "z", undefined, (t) => exactText(t("common:search.tooShort"))),
  paletteState("searching", QUERY, [hold("GET", SEARCH)], (t) => exactText(t("common:search.searching"))),
  paletteState(
    "empty",
    QUERY,
    [nothingFound([], "у персоны нет данных, где нашлось бы «zz»; ответ задан явно")],
    (t) => exactText(t("common:palette.empty", { query: QUERY })),
  ),
  paletteState(
    "kb-unavailable",
    QUERY,
    [nothingFound(["documents"], "поставщик поиска по базе знаний не отвечает; стенд записи его не запускает")],
    (t) => exactText(t("common:search.knowledgeUnavailable")),
  ),
];
