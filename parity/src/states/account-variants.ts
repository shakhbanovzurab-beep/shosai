// Варианты кабинета, рефералки, загрузок и горячих клавиш (шаг 3b): шрифты
// оформления, удаление аккаунта и данных, экспорт, загрузка, ошибки.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const EXPORT = "/v1/me/data/export";
const PERSONA_EMAIL = "free@parity.test";
const SPINNER = "main svg.spin";

/** Сборка в форме ответа черновика `GET /v1/app/builds`. */
const LINUX_BUILD = {
  id: "00000000-0000-4000-8000-000000000101",
  platform: "linux",
  platform_label: "Linux",
  version: "1.4.5",
  notes: "Стабильность записи и новые горячие клавиши.",
  file_name: "whisperer-1.4.5.AppImage",
  size_bytes: 96_468_992,
  is_current: true,
  download_url: "/v1/app/builds/00000000-0000-4000-8000-000000000101/download",
  published_at: "2026-07-12T12:00:00Z",
  created_at: "2026-07-12T12:00:00Z",
};

/** Плитка шрифта в «Общих»: адресуется атрибутом data-font, имя не переводится. */
function font(value: string): State {
  return {
    id: `account.cabinet.general.font-${value}`,
    fixture: "account/cabinet-general",
    scope: "single",
    overrides: [reply("PATCH", "/v1/me/profile", 200, { ok: true }, "ответ черновика на правку профиля — {ok: true} (api/me.py)")],
    act: async (page, { t }) => page.locator(cabinetDialog(t)).locator(`button[data-font="${value}"]`).click(),
    marker: () => `html[data-font="${value}"]`,
  };
}

/** Состояние панели экспорта при заданном ответе черновика о задании выгрузки. */
function exportJob(id: string, body: Record<string, string | number | null>, marker: (t: Translate) => string): State {
  return {
    id: `account.cabinet.data.export-${id}`,
    fixture: "account/cabinet-data",
    scope: "single",
    overrides: [reply("GET", EXPORT, 200, body, "задание выгрузки проходит стадии в фоновом обработчике, которого стенд не запускает")],
    marker,
  };
}

const exportBase = { created_at: "2026-07-17T11:50:00Z", download_url: null, expires_at: null, finished_at: null, size_bytes: 0 };

/** Подтверждение опасного действия: набрать почту и нажать кнопку окна. */
async function confirmDanger(page: Page, title: string, action: string): Promise<void> {
  const dialog = page.locator(`dialog[aria-label=${JSON.stringify(title)}]`);
  await dialog.locator("input").fill(PERSONA_EMAIL);
  await dialog.getByRole("button", { name: action }).click();
}

async function openCabinetAction(page: Page, { t }: StateContext, action: string): Promise<void> {
  await page.locator(cabinetDialog(t)).getByRole("button", { name: action }).click();
}

export const ACCOUNT_VARIANT_STATES: readonly State[] = [
  font("sans"),
  font("serif"),
  font("native"),
  font("mono"),
  {
    id: "account.cabinet.profile.delete-error",
    fixture: "account/cabinet-profile",
    scope: "single",
    expectsAlert: true,
    overrides: [serverError("DELETE", "/v1/me/data/account")],
    act: async (page, context) => {
      await openCabinetAction(page, context, context.t("account:cab.deleteAccountAction"));
      await confirmDanger(page, context.t("account:cab.deleteAccountTitle"), context.t("account:cab.deleteAccountAction"));
    },
    marker: alert((t) => t("account:cab.deleteAccountFailed")),
  },
  exportJob("pending", { ...exportBase, status: "pending" }, (t) => exactText(t("account:cab.exportPreparing"))),
  exportJob(
    "ready",
    {
      ...exportBase,
      status: "ready",
      download_url: "https://whisperer.one/v1/me/data/export/parity.zip",
      finished_at: "2026-07-17T11:55:00Z",
      expires_at: "2026-07-18T11:55:00Z",
      size_bytes: 4_718_592,
    },
    (t) => exactText(t("account:cab.exportDownload")),
  ),
  exportJob("failed", { ...exportBase, status: "failed" }, (t) => exactText(t("account:cab.exportFailed"))),
  {
    id: "account.cabinet.data.purge-confirm",
    fixture: "account/cabinet-data",
    scope: "full",
    act: async (page, context) => openCabinetAction(page, context, context.t("account:cab.purgeAction")),
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("account:cab.purgeTitle"))}]`,
  },
  {
    id: "account.cabinet.data.purge-done",
    fixture: "account/cabinet-data",
    scope: "single",
    overrides: [
      reply("POST", "/v1/me/data/purge", 200, { deleted: { sessions: 0, notes: 0 }, files_removed: 0 }, "удаление всех данных стенд записи не выполняет: оно необратимо"),
    ],
    act: async (page, context) => {
      await openCabinetAction(page, context, context.t("account:cab.purgeAction"));
      await confirmDanger(page, context.t("account:cab.purgeTitle"), context.t("account:cab.purgeAction"));
    },
    marker: (t) => withText("[role=status]", t("account:cab.purgeDone")),
  },
  {
    id: "account.cabinet.data.purge-failed",
    fixture: "account/cabinet-data",
    scope: "single",
    expectsAlert: true,
    overrides: [serverError("POST", "/v1/me/data/purge")],
    act: async (page, context) => {
      await openCabinetAction(page, context, context.t("account:cab.purgeAction"));
      await confirmDanger(page, context.t("account:cab.purgeTitle"), context.t("account:cab.purgeAction"));
    },
    marker: alert((t) => t("account:cab.purgeFailed")),
  },
  { id: "referral.loading", fixture: "referral/populated", scope: "full", overrides: [hold("GET", "/v1/me/referral")], marker: () => SPINNER },
  { id: "downloads.loading", fixture: "downloads/populated", scope: "full", overrides: [hold("GET", "/v1/app/builds")], marker: () => SPINNER },
  {
    id: "downloads.empty",
    fixture: "downloads/populated",
    scope: "full",
    overrides: [reply("GET", "/v1/app/builds", 200, [], "нет опубликованных сборок: состояние до первого релиза")],
    marker: (t) => exactText(t("downloads:download.empty")),
  },
  {
    id: "downloads.linux-limitations",
    fixture: "downloads/populated",
    scope: "single",
    overrides: [reply("GET", "/v1/app/builds", 200, [LINUX_BUILD], "сборка для Linux заморожена и в засеве не публикуется")],
    marker: (t) => withText("[role=note]", t("downloads:limitations.linux.title")),
  },
  { id: "hotkeys.loading", fixture: "hotkeys/populated", scope: "full", overrides: [hold("GET", "/v1/me/hotkeys")], marker: () => SPINNER },
  {
    id: "hotkeys.recording",
    fixture: "hotkeys/populated",
    scope: "single",
    act: async (page) => page.locator("main button").filter({ hasText: "⌘" }).first().click(),
    marker: (t) => exactText(t("hotkeys:hotkeys.recording")),
  },
  {
    id: "hotkeys.error-save",
    fixture: "hotkeys/save-rejected",
    scope: "single",
    // Ошибка стоит под списком из 22 строк: прокручиваем к ней, как человек.
    act: async (page, { t }) => {
      await page.locator("main button").filter({ hasText: "⌘" }).first().click();
      await page.keyboard.press("Alt+Meta+KeyJ");
      await page.locator(exactText(t("hotkeys:hotkeys.saveError"))).scrollIntoViewIfNeeded();
    },
    marker: (t) => exactText(t("hotkeys:hotkeys.saveError")),
  },
  {
    id: "route.error-fallback",
    fixture: "hotkeys/populated",
    scope: "full",
    overrides: [reply("GET", "/v1/me/hotkeys", 200, { hotkeys: {} }, "неполная карта сочетаний роняет раздел: так экран падает в границу отказа")],
    marker: (t) => exactText(t("common:common.loadError")),
  },
];
