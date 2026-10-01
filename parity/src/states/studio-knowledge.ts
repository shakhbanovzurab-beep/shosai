// База знаний (шаг 4): файлы, квота, источники, каталог, подключение источника.
// Квота, документы и источники засеяны; варианты — правки записанных ответов.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, reply } from "./overrides.ts";
import type { Override, State, StateContext } from "./types.ts";

const SPACE = "/v1/knowledge/space";
const DOCUMENTS = "/v1/knowledge/documents";
const SOURCES = "/v1/knowledge/sources";
const MIB = 1024 * 1024;

type Act = NonNullable<State["act"]>;

function kb(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `kb.${id}`, fixture: "studio/knowledge", scope: "single", marker, ...extra };
}

const sourcesTab: Act = async (page, { t }) => page.getByRole("button", { name: t("knowledge:kb.tabs.sources"), exact: true }).click();

/** Ни одного источника: весь каталог доступен для подключения. */
const noSources = reply("GET", SOURCES, 200, [], "источников ещё нет; при ошибке загрузки экран выглядит так же");

async function pickSpec(page: Page, context: StateContext, label: string): Promise<void> {
  await sourcesTab(page, context);
  await page.locator(`button:has-text(${JSON.stringify(label)}):enabled`).first().click();
}

const webForm = (t: Translate): string =>
  `dialog[aria-label=${JSON.stringify(t("knowledge:kb.sources.connectTitle", { name: "Веб-сайт" }))}]`;

const oauthSession = reply("POST", `${SOURCES}/oauth-session`, 200, { url: "https://accounts.google.com/o/oauth2/auth?parity=1" },
  "сеанс OAuth открывает Nango, которого на стенде нет");

/** Каталог → Google Drive → «Открыть Google Drive»: вкладка провайдера и ожидание доступа. */
const openGoogleDrive: Act = async (page, context) => {
  await pickSpec(page, context, "Google Drive");
  await page.getByRole("button", { name: context.t("knowledge:kb.sources.oauth.open", { name: "Google Drive" }) }).click();
};

const spaceMerge = (merge: { [key: string]: JsonValue }, reason: string): Override => ({ method: "GET", path: SPACE, respond: { merge }, reason });

export const STUDIO_KNOWLEDGE_STATES: readonly State[] = [
  kb("files.populated", () => 'text="Бюджет 2026.xlsx"', { scope: "full" }),
  { id: "kb.paywall", fixture: "studio/knowledge-free", scope: "full", marker: (t) => exactText(t("common:premium.title")) },
  kb("quota-almost-full", (t) => exactText(t("knowledge:kb.quota.almostFull")), {
    overrides: [spaceMerge({ used_bytes: 47 * MIB, used_ratio: 0.94 }, "место почти кончилось: те же документы, другая квота")],
  }),
  kb("not-ready", (t) => exactText(t("knowledge:kb.notReady")), {
    overrides: [spaceMerge({ ready: false }, "раздел ещё не подготовлен: признак готовности ставит первое подключение")],
  }),
  kb("files.loading", () => "main svg.spin", { overrides: [hold("GET", DOCUMENTS)] }),
  kb("files.empty", (t) => exactText(t("knowledge:kb.files.empty")), {
    overrides: [reply("GET", DOCUMENTS, 200, [], "документов ещё нет; при ошибке загрузки экран выглядит так же")],
  }),
  { id: "kb.files.highlight", fixture: "studio/knowledge-doc", scope: "single", marker: () => "[id^='kb-doc-'].border-primary" },
  kb("files.dragover", (t) => withText(".border-foreground", t("knowledge:kb.files.dropHere")), {
    act: async (page, { t }) =>
      page.getByText(t("knowledge:kb.files.dropHere")).evaluate((element) => {
        const transfer = new DataTransfer();
        transfer.items.add(new File(["x"], "план.md", { type: "text/markdown" }));
        element.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: transfer }));
      }),
  }),
  kb("files.upload-panel", (t) => `aside[aria-label=${JSON.stringify(t("common:uploads.title"))}]`, {
    overrides: [hold("POST", DOCUMENTS)],
    act: async (page) =>
      page.locator("main input[type=file]").first().setInputFiles({ name: "Бюджет 2027.xlsx", mimeType: "application/vnd.ms-excel", buffer: Buffer.alloc(2048, 1) }),
  }),
  kb("sources.populated", () => 'text="Рабочий vault"', { scope: "full", act: sourcesTab }),
  kb("sources.loading", () => "main svg.spin", { overrides: [hold("GET", SOURCES)], act: sourcesTab }),
  kb("sources.empty", (t) => exactText(t("knowledge:kb.sources.noneConnected")), { overrides: [noSources], act: sourcesTab }),
  kb("sources.syncing", () => ".animate-spin", {
    overrides: [hold("POST", `${SOURCES}/{source_id}/sync`)],
    act: async (page, context) => {
      await sourcesTab(page, context);
      const row = page.getByText("Рабочий vault", { exact: true }).locator("xpath=ancestor::div[.//button][1]");
      await row.getByRole("button", { name: context.t("knowledge:kb.sources.sync") }).click();
    },
  }),
  kb("sources.catalog-filter", () => 'button:has-text("Jira")', {
    act: async (page, context) => {
      await sourcesTab(page, context);
      await page.getByPlaceholder(context.t("knowledge:kb.sources.searchCatalog")).fill("Jira");
    },
  }),
  kb("sources.disconnect-confirm", (t) => exactText(t("knowledge:kb.sources.disconnectConfirm", { name: "Confluence ENG" })), {
    act: async (page, context) => {
      await sourcesTab(page, context);
      await page.getByRole("button", { name: context.t("knowledge:kb.sources.disconnect") }).first().click();
    },
  }),
  // Форму с полями в каталоге черновика имеет только «Веб-сайт»: остальные — OAuth.
  kb("connect.form", (t) => webForm(t), { overrides: [noSources], act: async (page, context) => pickSpec(page, context, "Веб-сайт") }),
  kb("connect.form-error", (t) => exactText(t("knowledge:kb.sources.errors.connector_upstream")), {
    overrides: [noSources, reply("POST", SOURCES, 502, { detail: "connector_upstream" }, "сайт источника не ответил; стенд в сеть не ходит")],
    act: async (page, context) => {
      await pickSpec(page, context, "Веб-сайт");
      const form = page.locator(webForm(context.t));
      await form.locator("input").last().fill("https://docs.example.com");
      await form.locator("button:enabled").last().click();
    },
  }),
  kb("connect.push-pending", (t) => exactText(t("knowledge:kb.sources.push.before")), {
    overrides: [noSources, hold("POST", SOURCES)],
    act: async (page, context) => pickSpec(page, context, "Obsidian"),
  }),
  kb("connect.push-token", (t) => `dialog[aria-label=${JSON.stringify(t("knowledge:kb.sources.push.title", { name: "Obsidian" }))}]`, {
    overrides: [
      noSources,
      reply("POST", SOURCES, 201, { id: "parity-source", kind: "obsidian", display_name: "Obsidian", status: "active", config: {},
        last_indexed_at: null, last_error: null, push_token: "wh_push_parity_token_0000" }, "токен плагина выдаёт черновик при подключении"),
    ],
    act: async (page, context) => pickSpec(page, context, "Obsidian"),
  }),
  kb("connect.oauth-intro", (t) => withText("button", t("knowledge:kb.sources.oauth.open", { name: "Google Drive" })), {
    act: async (page, context) => pickSpec(page, context, "Google Drive"),
  }),
  kb("connect.oauth-waiting", (t) => exactText(t("knowledge:kb.sources.oauth.waiting")), {
    overrides: [oauthSession, hold("GET", `${SOURCES}/oauth-folders`)],
    act: openGoogleDrive,
  }),
  kb("connect.oauth-folders", (t) => exactText(t("knowledge:kb.sources.oauth.folder")), {
    overrides: [
      oauthSession,
      reply("GET", `${SOURCES}/oauth-folders`, 200, [{ id: "parity-f1", name: "Проекты" }, { id: "parity-f2", name: "Бухгалтерия" }],
        "папки Диска отдаёт провайдер после входа; стенд в сеть не ходит"),
    ],
    act: openGoogleDrive,
  }),
];
