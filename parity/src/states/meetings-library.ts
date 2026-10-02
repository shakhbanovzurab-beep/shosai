// Библиотека встреч (шаг 4): список, загрузка и ошибка, папки, меню карточки и
// папки, подтверждения, тосты. Импорт записи — meetings-import.ts.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { STATUS } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const LIBRARY = "meetings/library";
const SESSIONS = "/v1/me/sessions";
const BUDGET_TITLE = "Планирование бюджета Q4";

const card = (title: string): string => `a.mtg-card-brand:has-text(${JSON.stringify(title)})`;
const folderRow = (name: string): string => `div[draggable]:has(button:has-text(${JSON.stringify(name)}))`;
const menu = "div.pop.fixed";

async function folderMenu(page: Page, { t }: StateContext, name: string): Promise<void> {
  await page.locator(folderRow(name)).first().getByRole("button", { name: t("meetings:meet.folders.rowMenu") }).click();
}

async function cardMenu(page: Page): Promise<void> {
  await page.locator(card(BUDGET_TITLE)).click({ button: "right" });
}

async function pick(page: Page, label: string): Promise<void> {
  await page.locator(menu).getByRole("button", { name: label, exact: true }).click();
}

const confirmDialog = (title: string): string => `dialog[open][aria-label=${JSON.stringify(title)}]`;

type Act = NonNullable<State["act"]>;

function library(id: string, act: Act, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.library.${id}`, fixture: LIBRARY, scope: "single", act, marker, ...extra };
}

export const MEETINGS_LIBRARY_STATES: readonly State[] = [
  { id: "meetings.library.populated", fixture: LIBRARY, scope: "full", sweep: true, marker: () => card(BUDGET_TITLE) },
  {
    id: "meetings.library.empty",
    fixture: "meetings/library-empty",
    scope: "full",
    marker: (t) => exactText(t("meetings:meet.library.emptyTitle")),
  },
  { id: "meetings.library.loading", fixture: LIBRARY, scope: "single", overrides: [hold("GET", SESSIONS)], marker: () => ".mtg svg.spin" },
  {
    id: "meetings.library.error",
    fixture: LIBRARY,
    scope: "single",
    overrides: [reply("GET", SESSIONS, 404, { detail: "Not Found" }, "4xx без повтора: так экран ошибки виден сразу")],
    marker: (t) => exactText(t("meetings:meet.library.loadError")),
  },
  library(
    "folder-expanded",
    async (page, { t }) => page.locator(folderRow("Работа")).first().getByRole("button", { name: t("meetings:meet.folders.expand") }).click(),
    () => `${folderRow("Юридическое")} >> nth=0`,
  ),
  library("folder-selected", async (page) => page.locator(`${folderRow("Финансы")} button:has-text("Финансы")`).first().click(),
    () => `${folderRow("Финансы")}.bg-primary`),
  library("folder-empty-selection", async (page) => page.locator(`${folderRow("Найм")} button:has-text("Найм")`).first().click(),
    (t) => exactText(t("meetings:meet.library.emptyFolder"))),
  library("folder-context-menu", async (page, context) => folderMenu(page, context, "Финансы"),
    (t) => withText(menu, t("meetings:meet.folders.favoriteRemove"))),
  library("folder-create-modal", async (page, { t }) => page.getByRole("button", { name: t("meetings:meet.folders.create"), exact: true }).first().click(),
    (t) => `dialog[aria-label=${JSON.stringify(t("meetings:meet.folders.create"))}]`),
  library(
    "folder-rename-modal",
    async (page, context) => {
      await folderMenu(page, context, "Финансы");
      await pick(page, context.t("meetings:meet.folders.rename"));
    },
    (t) => `dialog[aria-label=${JSON.stringify(t("meetings:meet.folders.renameTitle"))}]`,
  ),
  library(
    "folder-delete-confirm",
    async (page, context) => {
      await folderMenu(page, context, "Финансы");
      await pick(page, context.t("meetings:meet.folders.delete"));
    },
    (t) => confirmDialog(t("meetings:meet.folders.delete")),
  ),
  library("card-context-menu", async (page) => cardMenu(page), (t) => withText(menu, t("meetings:meet.library.menuToStorage"))),
  library(
    "card-rename-inline",
    async (page, { t }) => {
      await cardMenu(page);
      await pick(page, t("meetings:meet.library.menuRename"));
    },
    (t) => `input.mtg-card-rename[aria-label=${JSON.stringify(t("meetings:meet.library.renameField"))}]`,
  ),
  library(
    "delete-confirm",
    async (page, { t }) => {
      await cardMenu(page);
      await pick(page, t("common:actions.delete"));
    },
    (t) => confirmDialog(t("meetings:meet.library.deleteTitle")),
  ),
  library(
    "toast-saved",
    async (page, { t }) => {
      await cardMenu(page);
      await pick(page, t("meetings:meet.library.menuToStorage"));
    },
    (t) => withText(STATUS, t("meetings:meet.export.saved", { name: `${BUDGET_TITLE}.md` })),
    {
      overrides: [
        reply("POST", "/v1/me/sessions/{id}/save-to-storage", 200, { file_id: "parity-file", name: `${BUDGET_TITLE}.md`, size: 2048 },
          "файлы встречи пишутся в S3, которого на стенде нет"),
      ],
    },
  ),
  library(
    "toast-save-failed",
    async (page, { t }) => {
      await cardMenu(page);
      await pick(page, t("meetings:meet.library.menuToStorage"));
    },
    alert((t) => t("meetings:meet.export.saveFailed")),
    { expectsAlert: true, overrides: [serverError("POST", "/v1/me/sessions/{id}/save-to-storage")] },
  ),
  library(
    "toast-action-error",
    async (page, { t }) => {
      await cardMenu(page);
      await pick(page, t("common:actions.delete"));
      await page.locator(confirmDialog(t("meetings:meet.library.deleteTitle"))).getByRole("button", { name: t("common:actions.delete") }).click();
    },
    alert((t) => t("meetings:meet.library.actionError")),
    { expectsAlert: true, overrides: [serverError("DELETE", `${SESSIONS}/{id}`)] },
  ),
  {
    id: "meetings.library.mobile-folders-expanded",
    fixture: LIBRARY,
    scope: "single",
    viewports: ["mobile"],
    act: async (page, { t }) => page.locator(`button[aria-expanded]:has-text(${JSON.stringify(t("meetings:meet.library.folders"))})`).click(),
    marker: () => `${folderRow("Финансы")} >> nth=0`,
  },
];

