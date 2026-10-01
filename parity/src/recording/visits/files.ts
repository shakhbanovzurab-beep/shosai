// Визиты файлов, публичных ссылок на них и трекера. Состояния —
// parity/inventory/rooms-streams-storage-tracker.md.
//
// Файлов в хранилище нет (S3 у стенда нет): списки, квоты и ссылки черновик
// отдаёт из базы, а просмотр и скачивание задаёт состояние.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../../i18n/texts.ts";
import { boardUrl, SEED_IDS } from "../seed-ids.ts";
import type { Visit, VisitContext } from "./types.ts";

const tile = (name: string): string => `.stor-tile-btn[title=${JSON.stringify(name)}]`;
const sharedUrl = (key: string): string => `/app/s/${SEED_IDS.fileShares[key] ?? ""}`;
const storageTitle = (t: Translate): string => `h1:has-text(${JSON.stringify(t("storage:storage.title"))})`;

/** Открыть папку плиткой и дождаться её содержимого. */
async function enter(page: Page, folder: string, child: string): Promise<void> {
  await page.locator(tile(folder)).click();
  await page.locator(tile(child)).waitFor();
}

/**
 * Каждая папка грузит свой список: Acme с «Встречами» (видео, звук) и
 * «Договором» (PDF, DOCX), «Проекты» до скрипта на Python и архива; затем поиск.
 */
async function walkStorage(page: Page, { t }: VisitContext): Promise<void> {
  const crumb = (name: string) => page.getByRole("button", { name, exact: true });
  await enter(page, "Acme", "Договор");
  await enter(page, "Встречи", "Планирование_Q4.mp3");
  await crumb("/ Acme").click();
  await enter(page, "Договор", "Приложение_1_SLA.docx");
  await crumb(t("storage:storage.root")).click();
  await enter(page, "Проекты", "Архив_пилота_2025.zip");
  await enter(page, "Портал", "Скрипты");
  await enter(page, "Скрипты", "migrate_users.py");
  await crumb(t("storage:storage.root")).click();
  await page.locator(tile("Заметки.txt")).waitFor();
  await page.getByPlaceholder(t("storage:storage.searchPlaceholder"), { exact: true }).fill("Acme");
  await page.locator(tile("Логотип_Acme.png")).waitFor();
}

/** Общая ссылка с паролем: ввести пароль и открыть. */
const unlock = (password: string) => async (page: Page): Promise<void> => {
  await page.locator("form input[type=password]").fill(password);
  await page.locator("form button[type=submit]").click();
};

/** Обзор папки по ссылке: зайти в подпапку «Договор». */
async function openSharedSubfolder(page: Page): Promise<void> {
  await page.locator('button[title="Договор"]').click();
}

/**
 * Архив (пуст) и обратно к активным: каждый список — свой запрос. Наведение на
 * карточку заранее грузит её доску — меню карточки открывается так же.
 */
async function walkProjects(page: Page, { t }: VisitContext): Promise<void> {
  await page.getByRole("button", { name: t("tracker:tracker.project.showArchived"), exact: true }).click();
  await page.getByRole("button", { name: t("tracker:tracker.project.showActive"), exact: true }).click();
  await page.getByRole("button", { name: t("tracker:tracker.project.showArchived"), exact: true }).waitFor();
  const prefetch = page.waitForResponse((response) => response.url().endsWith("/board"));
  await page.locator('.trk-proj-card:has-text("Внедрение Acme")').hover();
  await prefetch;
}

/** Удалить колонку с задачами: черновик отказывает (422) и ничего не меняет. */
async function deleteBusyColumn(page: Page, { t }: VisitContext): Promise<void> {
  await page.locator(exactText(t("tracker:tracker.board.emptyColumn"))).waitFor();
  await page.locator(`button[title=${JSON.stringify(t("tracker:tracker.actions.columnMenu"))}]`).first().click();
  await page.getByRole("button", { name: t("tracker:tracker.actions.deleteColumn"), exact: true }).click();
}

export const FILES_VISITS: readonly Visit[] = [
  { id: "files/browser", persona: "lead", url: "/app/storage", marker: () => tile("Логотип_Acme.png"), act: walkStorage },
  { id: "files/quota", persona: "quota", url: "/app/storage", marker: storageTitle },
  { id: "files/overquota", persona: "overquota", url: "/app/storage", marker: storageTitle },
  { id: "files/locked-free", persona: "free", url: "/app/storage", marker: (t) => exactText(t("common:premium.title")) },
  { id: "files/locked-start", persona: "start", url: "/app/storage", marker: (t) => exactText(t("common:premium.storageTitle")) },

  { id: "files/shared-folder", persona: null, url: sharedUrl("folder"), marker: () => 'text="Приложение_1_SLA.docx"', act: openSharedSubfolder },
  {
    id: "files/shared-folder-locked",
    persona: null,
    url: sharedUrl("folderLocked"),
    marker: () => 'text="Архив_пилота_2025.zip"',
    act: unlock(SEED_IDS.sharePassword),
  },
  {
    id: "files/shared-file-locked",
    persona: null,
    url: sharedUrl("fileLocked"),
    marker: (t) => exactText(t("storage:sharedFile.wrong")),
    act: unlock("неверный"),
  },
  { id: "files/shared-file-view", persona: null, url: sharedUrl("fileView"), marker: (t) => exactText(t("storage:sharedFile.open")) },
  { id: "files/shared-gone", persona: null, url: sharedUrl("fileExpired"), marker: (t) => exactText(t("storage:sharedFile.gone")) },

  { id: "tracker/projects", persona: "lead", url: "/app/tracker", marker: () => 'text="Внедрение Acme"', act: walkProjects },
  {
    id: "tracker/board",
    persona: "lead",
    url: boardUrl("ACME"),
    marker: (t) => withText("[role=alert]", t("tracker:tracker.errors.columnDelete")),
    act: deleteBusyColumn,
  },
  { id: "tracker/board-portal", persona: "lead", url: boardUrl("PORTAL"), marker: () => 'h1:has-text("Портал")' },
  { id: "tracker/empty", persona: "free", url: "/app/tracker", marker: (t) => exactText(t("tracker:tracker.project.emptyTitle")) },
];
