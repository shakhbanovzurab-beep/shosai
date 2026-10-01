// Публичная страница ссылки на файл или папку (шаг 6): загрузка, пароль,
// неверный пароль, обзор папки и подпапки, недействительная ссылка.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../i18n/texts.ts";
import { SEED_IDS } from "../recording/seed-ids.ts";
import { hold, reply } from "./overrides.ts";
import type { State } from "./types.ts";

const LIST = "/v1/storage/shared/{token}/list";

function shared(id: string, fixture: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `shared.${id}`, fixture: `files/${fixture}`, scope: "single", marker, ...extra };
}

/** Ввести пароль и отправить форму. */
const unlock = (password: string) => async (page: Page): Promise<void> => {
  await page.locator("form input[type=password]").fill(password);
  await page.locator("form button[type=submit]").click();
};

export const SHARED_FILES_STATES: readonly State[] = [
  shared("loading", "shared-folder", () => ".rise svg.spin", { overrides: [hold("GET", "/v1/storage/shared/{token}/meta")] }),
  shared("gone", "shared-gone", (t) => exactText(t("storage:sharedFile.gone")), { scope: "full" }),
  shared("file.password", "shared-file-locked", (t) => exactText(t("storage:sharedFile.download")), { scope: "full" }),
  shared("file.wrong", "shared-file-locked", (t) => exactText(t("storage:sharedFile.wrong")), { act: unlock("неверный") }),
  // Страницу ссылки на файл черновик открывает только для ссылок с паролем.
  shared("file.view-only", "shared-file-view", (t) => exactText(t("storage:sharedFile.open")), {
    overrides: [{ method: "GET", path: "/v1/storage/shared/{token}/meta", reason: "засеянная ссылка без пароля; экран тот же, что у ссылки с паролем", respond: { merge: { needs_password: true } } }],
  }),
  shared("folder.password", "shared-folder-locked", (t) => exactText(t("storage:sharedFile.openFolder"))),
  shared("folder.unlocked", "shared-folder-locked", () => 'button[title="Архив_пилота_2025.zip"]', { act: unlock(SEED_IDS.sharePassword) }),
  shared("folder.browsing", "shared-folder", () => 'button[title="Логотип_Acme.png"]', { scope: "full" }),
  shared("folder.subfolder", "shared-folder", () => 'button[title="Приложение_1_SLA.docx"]', {
    act: async (page) => page.locator('button[title="Договор"]').click(),
  }),
  shared("folder.empty", "shared-folder", (t) => exactText(t("storage:sharedFile.folderEmpty")), {
    overrides: [{ method: "GET", path: LIST, reason: "в засеянной папке есть файлы", respond: { merge: { entries: [] } } }],
  }),
  shared("folder.list-loading", "shared-folder", () => ".rise svg.spin", { overrides: [hold("GET", LIST)] }),
  shared("folder.gone", "shared-folder", (t) => exactText(t("storage:sharedFile.gone")), {
    overrides: [reply("GET", LIST, 200, { found: false }, "ссылку отозвали, пока страница была открыта")],
  }),
];
