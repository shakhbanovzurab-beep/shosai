// MCP (шаг 5): вкладка кабинета — свой сервер и внешние серверы, экран согласия
// OAuth для внешнего AI, переадресации.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog } from "../ui/draft-ui.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const SERVER = "/v1/me/mcp/server";
const CLIENTS = "/v1/me/mcp/clients";
const AUTHORIZE = "/v1/mcp/oauth/authorize";

const inCabinet = (t: Translate, selector: string): string => `${cabinetDialog(t)} >> ${selector}`;
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });

function mcp(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `mcp.${id}`, fixture: "cabinet/mcp", scope: "single", marker, ...extra };
}

function consent(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `mcp.consent.${id}`, fixture: "mcp/consent", scope: "single", marker, ...extra };
}

async function clientTab(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("mcp:cab.mcp.tab.client")).click();
}

/** Новый токен показывается один раз целиком; остальное — как у засеянного сервера. */
const ROTATED = {
  endpoint: "http://parity.localhost/mcp",
  token: "whmcp_parity_rotated_token_000000000000000000",
  expiresAt: "2027-07-17T12:00:00+00:00",
  exposedResources: [
    { key: "meetings", label: "Встречи", enabled: true },
    { key: "notes", label: "Заметки", enabled: true },
    { key: "transcripts", label: "Стенограммы", enabled: false },
    { key: "action_items", label: "Задачи", enabled: false },
  ],
};

export const MCP_STATES: readonly State[] = [
  mcp("server.populated", (t) => inCabinet(t, exactText(t("mcp:cab.mcp.server.exposedTitle"))), { scope: "full" }),
  mcp("server.loading", (t) => inCabinet(t, "svg.spin"), { overrides: [hold("GET", SERVER)] }),
  mcp("server.token-revealed", (t) => `button[aria-label=${JSON.stringify(t("mcp:cab.mcp.server.hide"))}]`, {
    act: async (page, { t }) => page.locator(`button[aria-label=${JSON.stringify(t("mcp:cab.mcp.server.show"))}]`).click(),
  }),
  mcp("server.rotated", (t) => inCabinet(t, withText("*", t("mcp:cab.mcp.server.rotated"))), {
    overrides: [reply("POST", `${SERVER}/rotate`, 200, ROTATED, "новый токен случаен; стенд записи его не выпускал")],
    act: async (page, { t }) => page.locator(`button[aria-label=${JSON.stringify(t("mcp:cab.mcp.server.rotate"))}]`).click(),
  }),
  mcp("client.populated", () => 'text="Docs MCP"', { scope: "full", act: clientTab }),
  mcp("client.empty", (t) => exactText(t("mcp:cab.mcp.client.emptyTitle")), {
    overrides: [reply("GET", CLIENTS, 200, [], "у засеянной персоны есть внешние серверы")],
    act: clientTab,
  }),
  mcp("client.add-error", (t) => inCabinet(t, withText("*", t("mcp:cab.mcp.client.addFailed"))), {
    overrides: [reply("POST", CLIENTS, 422, { detail: "dns_failed" }, "адрес сервера проверяется по DNS; у стенда нет сети")],
    act: async (page, context) => {
      await clientTab(page, context);
      await page.getByLabel(context.t("mcp:cab.mcp.client.name"), { exact: true }).fill("Jira MCP");
      await page.getByLabel(context.t("mcp:cab.mcp.client.url"), { exact: true }).fill("https://mcp.atlassian.com/v1/sse");
      await button(page, context.t("mcp:cab.mcp.client.add")).click();
    },
  }),
  mcp("client.oauth-start", (t) => `button:has-text(${JSON.stringify(t("calendar:calendar.integrations.connect"))}) svg.spin`, {
    overrides: [hold("POST", `${CLIENTS}/{id}/oauth/start`)],
    act: async (page, context) => {
      await clientTab(page, context);
      await button(page, context.t("calendar:calendar.integrations.connect")).first().click();
    },
  }),
  mcp("client.oauth-return", (t) => withText("[role=status]", t("leo:skills.attached")), {
    url: "/app/cabinet/mcp?mcp_connect=ok",
    act: clientTab,
  }),
  // /settings/mcp — старый адрес вкладки: переадресация с сохранением запроса.
  mcp("settings-redirect", (t) => inCabinet(t, exactText(t("mcp:cab.mcp.server.exposedTitle"))), { url: "/app/settings/mcp" }),
  {
    id: "mcp.free-redirect",
    fixture: "account/cabinet-general",
    url: "/app/cabinet/mcp",
    scope: "single",
    marker: (t) => inCabinet(t, withText("*", t("account:cab.appearance"))),
  },

  consent("ready", (t) => withText("button", t("mcp:cab.mcp.consent.allow")), { scope: "full" }),
  consent("loading", () => "svg.spin", { overrides: [hold("GET", AUTHORIZE)] }),
  consent("error", (t) => exactText(t("mcp:cab.mcp.consent.errorTitle")), {
    overrides: [reply("GET", AUTHORIZE, 400, { detail: "invalid_client" }, "ссылка с неизвестным клиентом; засеян только «Claude»")],
  }),
  consent("working", (t) => `button:has-text(${JSON.stringify(t("mcp:cab.mcp.consent.allow"))}) svg.spin`, {
    overrides: [hold("POST", AUTHORIZE)],
    act: async (page, { t }) => button(page, t("mcp:cab.mcp.consent.allow")).click(),
  }),
];
