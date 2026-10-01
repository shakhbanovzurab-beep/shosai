// «Файлы» (шаг 6): обзор хранилища плиткой и списком, папки, поиск, квоты,
// замки тарифа, выделение, меню и окна действий. Просмотр файлов и ссылки —
// storage-viewer.ts, публичные страницы ссылок — shared-files.ts.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

export const LIST = "/v1/me/storage/list";
const NOTES_ID = "00000000-0000-4000-8000-000000000021";

export const tile = (name: string): string => `.stor-tile-btn[title=${JSON.stringify(name)}]`;
export const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
export const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });
const tileBox = (name: string): string => `[data-storage-id]:has(${tile(name)})`;

function browser(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `storage.${id}`, fixture: "files/browser", scope: "single", marker, ...extra };
}

/** Открыть папку плиткой и дождаться плитки внутри неё. */
export async function enter(page: Page, folder: string, child: string): Promise<void> {
  await page.locator(tile(folder)).click();
  await page.locator(tile(child)).waitFor();
}

/** Меню элемента правой кнопкой — как его открывает человек. */
export async function itemMenu(page: Page, name: string): Promise<void> {
  await page.locator(tile(name)).click({ button: "right" });
}

const menuAction = (name: string, item: (t: Translate) => string) => async (page: Page, { t }: StateContext): Promise<void> => {
  await itemMenu(page, name);
  await button(page, item(t)).click();
};

async function select(page: Page, ...names: string[]): Promise<void> {
  for (const name of names) await page.locator(`${tileBox(name)} .stor-check`).click();
}

const KNOWLEDGE = "/v1/me/storage/knowledge";
const KNOWLEDGE_REASON = "отправка в Базу знаний читает файл из S3; у стенда записи его нет";

export const STORAGE_STATES: readonly State[] = [
  browser("browser.grid", () => tile("Смета_пилота_Acme_v2.xlsx"), { scope: "full" }),
  browser("browser.loading", () => "svg.spin", {
    overrides: [hold("GET", LIST)],
  }),
  browser("browser.empty", (t) => exactText(t("storage:storage.drop.dropHere")), {
    overrides: [reply("GET", LIST, 200, [], "у засеянной персоны есть файлы")],
  }),
  browser("browser.list", () => `tr.stor-row:has-text("Смета_пилота_Acme_v2.xlsx")`, {
    act: async (page, { t }) => page.locator(`button[aria-label=${JSON.stringify(t("storage:storage.view.list"))}]`).click(),
  }),
  browser("browser.subfolder", () => tile("Логотип_Acme.png"), { act: async (page) => enter(page, "Acme", "Логотип_Acme.png") }),
  browser("browser.nested", () => tile("migrate_users.py"), {
    act: async (page) => {
      await enter(page, "Проекты", "Портал");
      await enter(page, "Портал", "Скрипты");
      await enter(page, "Скрипты", "migrate_users.py");
    },
  }),
  browser("browser.search", () => tile("Демо_Acme.mp4"), {
    act: async (page, { t }) => page.getByPlaceholder(t("storage:storage.searchPlaceholder"), { exact: true }).fill("Acme"),
  }),
  browser("browser.search-empty", (t) => `input[placeholder=${JSON.stringify(t("storage:storage.searchPlaceholder"))}][value="Отчёт"]`, {
    overrides: [{ method: "GET", path: LIST, reason: "поиск по засеянному хранилищу что-то находит", respond: ["recorded", { status: 200, body: [] }] }],
    act: async (page, { t }) => page.getByPlaceholder(t("storage:storage.searchPlaceholder"), { exact: true }).fill("Отчёт"),
  }),
  browser("browser.sort-size", () => tile("Созвон с Acme.mp4"), {
    act: async (page, { t }) => {
      await page.getByRole("combobox", { name: t("storage:storage.sort.label"), exact: true }).click();
      await page.getByRole("option", { name: t("storage:storage.sort.size"), exact: true }).click();
    },
  }),
  { id: "storage.quota.danger", fixture: "files/quota", scope: "single", marker: (t) => exactText(t("storage:storage.drop.dropHere")) },
  { id: "storage.quota.over", fixture: "files/overquota", scope: "single", marker: (t) => exactText(t("storage:storage.quota.over")) },
  { id: "storage.locked.free", fixture: "files/locked-free", scope: "full", marker: (t) => exactText(t("common:premium.title")) },
  { id: "storage.locked.no-quota", fixture: "files/locked-start", scope: "single", marker: (t) => exactText(t("common:premium.storageTitle")) },

  browser("selection-bar", (t) => withText(".stor-selbar", t("storage:storage.selected", { count: 2 })), {
    act: async (page) => select(page, "Заметки.txt", "Смета_пилота_Acme_v2.xlsx"),
  }),
  browser("upload-menu", (t) => withText("div.pop", t("storage:storage.drop.pickFolder")), {
    act: async (page, { t }) => button(page, t("storage:storage.upload")).click(),
  }),
  browser("context-menu.file", (t) => withText("div.pop", t("storage:storage.row.toKnowledge")), {
    act: async (page) => itemMenu(page, "Заметки.txt"),
  }),
  browser("context-menu.folder", (t) => withText("div.pop", t("storage:storage.row.share")), {
    act: async (page) => itemMenu(page, "Личное"),
  }),
  browser("context-menu.shared", (t) => withText("div.pop", t("storage:storage.row.unshare")), {
    act: async (page) => itemMenu(page, "Acme"),
  }),
  browser("dialog.new-folder", (t) => dialog(t("storage:storage.newFolder")), {
    act: async (page, { t }) => button(page, t("storage:storage.newFolder")).click(),
  }),
  browser("dialog.rename", (t) => dialog(t("storage:storage.row.rename")), {
    act: menuAction("Заметки.txt", (t) => t("storage:storage.row.rename")),
  }),
  browser("dialog.delete", (t) => withText(dialog(t("storage:storage.row.delete")), t("storage:storage.deleteConfirm", { name: "Заметки.txt" })), {
    act: menuAction("Заметки.txt", (t) => t("storage:storage.row.delete")),
  }),
  browser("dialog.bulk-delete", (t) => withText(dialog(t("storage:storage.row.delete")), t("storage:storage.bulkDeleteConfirm", { count: 2 })), {
    act: async (page, { t }) => {
      await select(page, "Заметки.txt", "Смета_пилота_Acme_v2.xlsx");
      await page.locator(".stor-selbar").getByRole("button", { name: t("storage:storage.row.delete"), exact: true }).click();
    },
  }),
  browser("dialog.move", (t) => withText(dialog(t("storage:storage.moveModal.title", { name: "Заметки.txt" })), "Личное"), {
    act: menuAction("Заметки.txt", (t) => t("storage:storage.move")),
  }),
  browser("dialog.bulk-move", (t) => withText(dialog(t("storage:storage.bulkMoveTitle", { count: 2 })), "Личное"), {
    act: async (page, { t }) => {
      await select(page, "Заметки.txt", "Смета_пилота_Acme_v2.xlsx");
      await page.locator(".stor-selbar").getByRole("button", { name: t("storage:storage.move"), exact: true }).click();
    },
  }),
  browser("toast.action-error", (t) => withText("[role=alert]", t("storage:storage.actionError")), {
    expectsAlert: true,
    overrides: [serverError("PATCH", "/v1/me/storage/{id}")],
    act: async (page, context) => {
      await menuAction("Заметки.txt", (t) => t("storage:storage.row.rename"))(page, context);
      const rename = page.locator(dialog(context.t("storage:storage.row.rename")));
      await rename.locator("input").fill("Заметки по Acme.txt");
      await rename.getByRole("button", { name: context.t("storage:storage.save"), exact: true }).click();
    },
  }),
  browser("toast.knowledge-sent", (t) => withText("[role=status]", t("storage:storage.knowledge.sent", { count: 1 })), {
    overrides: [reply("POST", KNOWLEDGE, 200, { sent: [NOTES_ID], skipped: [] }, KNOWLEDGE_REASON)],
    act: menuAction("Заметки.txt", (t) => t("storage:storage.row.toKnowledge")),
  }),
  browser("toast.knowledge-skipped", (t) => withText("[role=alert]", t("storage:storage.knowledge.reason.unsupported_type")), {
    expectsAlert: true,
    overrides: [reply("POST", KNOWLEDGE, 200, {
      sent: [],
      skipped: [{ file_id: "00000000-0000-4000-8000-000000000026", name: "Созвон с Acme.mp4", reason: "unsupported_type" }],
    }, "запись стенда не отправляла файлы в Базу знаний; ответ — как у черновика для видео")],
    act: menuAction("Созвон с Acme.mp4", (t) => t("storage:storage.row.toKnowledge")),
  }),
];
