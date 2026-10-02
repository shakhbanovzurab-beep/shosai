// «Файлы» (шаг 6): просмотр файла каждого вида и окно ссылки на файл или папку.
//
// S3 у стенда записи нет: черновик отдаёт пустое содержимое и 500 на подписанную
// ссылку. Поэтому содержимое и ссылку задаёт состояние: текст и документы Office —
// ответом content, картинку и PDF — ссылкой на подставное хранилище объектов
// (serve/object-store.ts). Видео и звук стенд не декодирует — снимается плеер.

import type { Page } from "@playwright/test";

import { withText, type Translate } from "../i18n/texts.ts";
import { estimateXlsx, slaDocx } from "../samples/office.ts";
import { objectUrl } from "../serve/object-store.ts";
import { binary, content, hold, reply, serverError } from "./overrides.ts";
import { button, dialog, enter, itemMenu, tile } from "./storage.ts";
import type { Override, State, StateContext } from "./types.ts";

const CONTENT = "/v1/me/storage/content/{id}";
const DOWNLOAD_URL = "/v1/me/storage/download-url/{id}";
const S3_REASON = "файл лежит в S3, а у стенда записи его нет";

const viewUrl = (key: string): Override => reply("GET", DOWNLOAD_URL, 200, { url: objectUrl(key) }, S3_REASON);

const NOTES = [
  "Созвон с Acme — 15 июля",
  "",
  "1. Тестовый доступ к API открываем до 20 июля.",
  "2. SSO через Azure AD — после согласования с безопасностью.",
  "3. Обучение администраторов: две группы по 10 человек.",
].join("\n");

const MIGRATE = [
  '"""Перенос пользователей Acme по отделам."""',
  "",
  "import csv",
  "",
  "",
  "def migrate(path: str) -> int:",
  "    moved = 0",
  "    with open(path, encoding=\"utf-8\") as source:",
  "        for row in csv.DictReader(source):",
  "            print(row[\"email\"], row[\"department\"])",
  "            moved += 1",
  "    return moved",
].join("\n");

const viewer = (name: string): string => dialog(name);

function view(id: string, marker: (t: Translate) => string, open: (page: Page) => Promise<void>, overrides: readonly Override[]): State {
  return { id: `storage.viewer.${id}`, fixture: "files/browser", scope: "single", marker, overrides, act: async (page) => open(page) };
}

const openTile = (name: string, ...path: readonly (readonly [string, string])[]) => async (page: Page): Promise<void> => {
  for (const [folder, child] of path) await enter(page, folder, child);
  await page.locator(tile(name)).click();
};

function share(id: string, marker: (t: Translate) => string, act: (page: Page, context: StateContext) => Promise<void>, extra: Partial<State> = {}): State {
  return { id: `storage.share.${id}`, fixture: "files/browser", scope: "single", marker, act, ...extra };
}

async function openShare(page: Page, { t }: StateContext, name = "Заметки.txt"): Promise<void> {
  await itemMenu(page, name);
  await button(page, t("storage:storage.row.share")).click();
}

async function openSecurity(page: Page, context: StateContext): Promise<void> {
  await openShare(page, context);
  await page.getByText(context.t("storage:storage.share.security"), { exact: true }).click();
}

const SHARE = "/v1/me/storage/{id}/share";
const SHARE_REASON = "ссылку на файл без неё черновик заводит со случайным токеном";
const shareResponse = (downloadDisabled: boolean): Override => reply("POST", SHARE, 200, {
  share_url: "http://parity.localhost/v1/storage/shared/parity-file-notes",
  token: "parity-file-notes",
  share_has_password: false,
  share_expires_at: null,
  share_download_disabled: downloadDisabled,
}, SHARE_REASON);

export const STORAGE_VIEWER_STATES: readonly State[] = [
  view("loading", () => `${viewer("Заметки.txt")} svg.spin`, openTile("Заметки.txt"), [hold("GET", CONTENT)]),
  view("error", (t) => withText(viewer("Скриншот_дашборда.jpg"), t("storage:storage.viewer.error")), openTile("Скриншот_дашборда.jpg"), [serverError("GET", DOWNLOAD_URL)]),
  view("code", () => `${viewer("Заметки.txt")} .cm-content:has-text("Обучение администраторов")`, openTile("Заметки.txt"),
    [content("GET", CONTENT, NOTES, "text/plain; charset=utf-8", S3_REASON)]),
  view("code-python", () => `${viewer("migrate_users.py")} .cm-content:has-text("DictReader")`,
    openTile("migrate_users.py", ["Проекты", "Портал"], ["Портал", "Скрипты"], ["Скрипты", "migrate_users.py"]),
    [content("GET", CONTENT, MIGRATE, "text/x-python; charset=utf-8", S3_REASON)]),
  view("pdf", () => `${viewer("Прайс_2025.pdf")} object`, openTile("Прайс_2025.pdf"), [viewUrl("/price-2025.pdf")]),
  view("image", () => `${viewer("Логотип_Acme.png")} img`, openTile("Логотип_Acme.png", ["Acme", "Логотип_Acme.png"]), [viewUrl("/acme/logo.png")]),
  view("video", () => `${viewer("Созвон с Acme.mp4")} video`, openTile("Созвон с Acme.mp4"), [viewUrl("/meetings/call-acme.mp4")]),
  view("audio", () => `${viewer("Планирование_Q4.mp3")} audio`,
    openTile("Планирование_Q4.mp3", ["Acme", "Встречи"], ["Встречи", "Планирование_Q4.mp3"]), [viewUrl("/meetings/q4-planning.mp3")]),
  view("docx", () => `${viewer("Приложение_1_SLA.docx")} .md-content table`,
    openTile("Приложение_1_SLA.docx", ["Acme", "Договор"], ["Договор", "Приложение_1_SLA.docx"]),
    [binary("GET", CONTENT, slaDocx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", S3_REASON)]),
  view("sheet", () => `${viewer("Смета_пилота_Acme_v2.xlsx")} .md-content table`, openTile("Смета_пилота_Acme_v2.xlsx"),
    [binary("GET", CONTENT, estimateXlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", S3_REASON)]),
  view("no-preview", (t) => withText(viewer("Архив_пилота_2025.zip"), t("storage:storage.viewer.noPreview")),
    openTile("Архив_пилота_2025.zip", ["Проекты", "Архив_пилота_2025.zip"]), []),
  {
    id: "storage.viewer.save-error",
    fixture: "files/browser",
    scope: "single",
    marker: (t) => withText("[role=alert]", t("storage:storage.viewer.saveError")),
    expectsAlert: true,
    overrides: [
      content("GET", CONTENT, NOTES, "text/plain; charset=utf-8", S3_REASON),
      reply("PUT", CONTENT, 503, { detail: "storage_unavailable" }, "сохранение пишет в S3; ответ — как у черновика без него"),
    ],
    act: async (page, { t }) => {
      await openTile("Заметки.txt")(page);
      await page.locator(".cm-content").click();
      await page.keyboard.press("Control+End");
      await page.keyboard.type("\n4. Итоги пилота — к 1 сентября.");
      await page.locator(viewer("Заметки.txt")).getByRole("button", { name: t("storage:storage.save"), exact: true }).click();
    },
  },

  share("main", (t) => withText(dialog(t("storage:storage.share.title")), t("storage:storage.share.viewHint")), openShare),
  share("main-folder", (t) => dialog(t("storage:storage.share.titleFolder")), async (page, context) => openShare(page, context, "Личное")),
  share("security", (t) => withText(dialog(t("storage:storage.share.title")), t("storage:storage.share.passwordHint")), openSecurity),
  share("qr", (t) => `svg[role=img][aria-label=${JSON.stringify(t("storage:storage.share.qr"))}]`, async (page, context) => {
    await openShare(page, context);
    await button(page, context.t("storage:storage.share.qr")).click();
  }, { overrides: [shareResponse(false)] }),
  share("saved", (t) => withText("[role=status]", t("storage:storage.share.saved")), async (page, context) => {
    await openSecurity(page, context);
    await page.getByText(context.t("storage:storage.share.noDownload"), { exact: true }).click();
    await button(page, context.t("storage:storage.share.save")).click();
  }, { overrides: [shareResponse(true)] }),
  share("save-error", (t) => withText("[role=alert]", t("storage:storage.share.saveFailed")), async (page, context) => {
    await openSecurity(page, context);
    await button(page, context.t("storage:storage.share.save")).click();
  }, { expectsAlert: true, overrides: [serverError("POST", SHARE)] }),
  // Буфер обмена без разрешения отказывает — так копирование и не удаётся у человека.
  share("copy-failed", (t) => withText("[role=alert]", t("storage:storage.share.copyFailed")), async (page, context) => {
    await openShare(page, context);
    await button(page, context.t("storage:storage.share.copy")).click();
  }, { expectsAlert: true, overrides: [shareResponse(false)] }),
  // «Удалить» в окне ждёт ссылку: её заводит QR-код, затем — назад и удалить.
  // У уже расшаренного файла меню предлагает «Закрыть доступ» без окна и без тоста.
  share("revoked", (t) => withText("[role=status]", t("storage:storage.share.revoked")), async (page, context) => {
    await openShare(page, context);
    await button(page, context.t("storage:storage.share.qr")).click();
    await page.getByTitle(context.t("storage:storage.share.back"), { exact: true }).click();
    await button(page, context.t("storage:storage.share.revoke")).click();
  }, { overrides: [shareResponse(false), reply("DELETE", SHARE, 204, null, "удаление ссылки меняет данные засева, общие для других визитов")] }),
];
