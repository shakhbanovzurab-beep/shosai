// Действия в кабинете (шаг 3b): рассылки, сохранение имени, аватар, запрос
// выгрузки, отказ сохранить настройку приватности.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog, STATUS } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const PROFILE = "/v1/me/profile";
const AVATAR = "/v1/me/avatar";

const saved = reply("PATCH", PROFILE, 200, { ok: true }, "ответ черновика на правку профиля — {ok: true} (api/me.py)");

function cabinetSwitch(t: Translate, label: string): string {
  return `${cabinetDialog(t)} [role=switch][aria-label=${JSON.stringify(label)}]`;
}

/** Картинка 1×1 PNG: аватар выбирается из файла, содержимое ответу безразлично. */
const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function pickAvatar(page: Page, { t }: StateContext): Promise<void> {
  await page
    .locator(`${cabinetDialog(t)} input[type=file][aria-label=${JSON.stringify(t("account:cab.uploadAvatar"))}]`)
    .setInputFiles({ name: "avatar.png", mimeType: "image/png", buffer: PIXEL });
}

async function clickCabinet(page: Page, { t }: StateContext, name: string): Promise<void> {
  await page.locator(cabinetDialog(t)).getByRole("button", { name }).click();
}

export const ACCOUNT_ACTION_STATES: readonly State[] = [
  {
    id: "account.cabinet.general.marketing-on",
    fixture: "account/cabinet-general",
    scope: "single",
    overrides: [saved],
    act: async (page, { t }) => page.locator(cabinetSwitch(t, t("account:cab.marketingLabel"))).click(),
    marker: (t) => `${cabinetSwitch(t, t("account:cab.marketingLabel"))}[aria-checked=true]`,
  },
  {
    id: "account.cabinet.profile.saving",
    fixture: "account/cabinet-profile",
    scope: "single",
    overrides: [hold("PATCH", PROFILE)],
    act: async (page, { t }) =>
      page.locator(cabinetDialog(t)).getByRole("textbox", { name: t("account:cab.nameLabel") }).fill("Анна Смирнова-Орлова"),
    marker: (t) => `${cabinetDialog(t)} >> ${exactText(t("account:cab.saving"))}`,
  },
  {
    id: "account.cabinet.profile.avatar-uploading",
    fixture: "account/cabinet-profile",
    scope: "single",
    overrides: [hold("POST", AVATAR)],
    act: pickAvatar,
    marker: (t) => withText(`${cabinetDialog(t)} button`, t("account:cab.uploading")),
  },
  {
    id: "account.cabinet.profile.avatar-error",
    fixture: "account/cabinet-profile",
    scope: "single",
    overrides: [reply("POST", AVATAR, 413, { detail: "File too large" }, "слишком большой файл; стенд записи загрузок не делает")],
    act: pickAvatar,
    marker: (t) => `${cabinetDialog(t)} >> ${exactText(t("account:cab.avatarError"))}`,
  },
  {
    id: "account.cabinet.data.export-requested",
    fixture: "account/cabinet-data",
    scope: "single",
    overrides: [
      reply(
        "POST",
        "/v1/me/data/export",
        202,
        { status: "pending", created_at: "2026-07-17T12:00:00Z", download_url: null, expires_at: null, finished_at: null, size_bytes: 0 },
        "задание выгрузки стенд записи не запускает: архив собирает фоновый обработчик",
      ),
    ],
    act: async (page, context) => clickCabinet(page, context, context.t("account:cab.exportRequest")),
    marker: (t) => withText(STATUS, t("account:cab.exportQueued")),
  },
  {
    id: "account.cabinet.data.toggle-error",
    fixture: "account/cabinet-data",
    scope: "single",
    expectsAlert: true,
    overrides: [serverError("PATCH", PROFILE)],
    act: async (page, { t }) => page.locator(cabinetSwitch(t, t("account:cab.noLogsLabel"))).click(),
    marker: alert((t) => t("account:cab.noLogsFailed")),
  },
];
