// Вкладка Leo кабинета (шаг 5): персонализация, сервисы, инициатива, почта,
// уведомления, память, поручения, расширенные настройки. Вкладка длиннее окна:
// состояния блоков прокручивают кабинет к своему блоку. Окна памяти — leo-memory.ts.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog } from "../ui/draft-ui.ts";
import { hold, reply } from "./overrides.ts";
import type { State } from "./types.ts";

const FIXTURE = "cabinet/leo";
const SETTINGS = "/v1/proactive/settings";

const inCabinet = (t: Translate, selector: string): string => `${cabinetDialog(t)} >> ${selector}`;
const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;

export function cab(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `leo.cab.${id}`, fixture: FIXTURE, scope: "single", marker, ...extra };
}

/**
 * Блок ниже края окна: маркер — его текст, кабинет прокручивается к нему.
 * `:text()` берёт самый вложенный элемент с текстом: у `:has-text()` первым
 * совпал бы весь кабинет, и прокручивать было бы нечего.
 */
const block = (id: string, text: (t: Translate) => string, extra: Partial<State> = {}): State =>
  cab(id, (t) => inCabinet(t, `:text(${JSON.stringify(text(t))})`), { reveal: true, ...extra });

const button = (page: Page, name: string): ReturnType<Page["getByRole"]> =>
  page.getByRole("button", { name, exact: true });

/** Настройки инициативы в форме ответа черновика; правка — поверх засеянных. */
function settings(patch: Readonly<Record<string, string | boolean>>): { [key: string]: JsonValue } {
  return {
    level: "reserved",
    muted_kinds: ["hub_looping"],
    channels: ["in_app"],
    quiet_from: "22:00:00",
    quiet_to: "08:00:00",
    quiet_enabled: true,
    notification_preview: true,
    ...patch,
  };
}

const SAVED = "сохранение настройки отвечает тем, что сохранено; стенд записи его не выполнял";

const CATALOGUE: readonly (readonly [string, string, string, readonly string[]])[] = [
  ["google-mail", "Gmail", "Почта", ["mail.read", "mail.send"]],
  ["outlook", "Outlook", "Почта", ["calendar.read", "calendar.write", "mail.read", "mail.send"]],
  ["google-drive", "Google Drive", "Файлы", ["files.read", "files.write"]],
  ["dropbox", "Dropbox", "Файлы", ["files.read", "files.write"]],
  ["notion", "Notion", "Заметки", ["notes.write"]],
  ["confluence", "Confluence", "Заметки", ["notes.write"]],
  ["slack", "Slack", "Общение", ["chat.send"]],
  ["github", "GitHub", "Задачи", ["tasks.write"]],
  ["gitlab", "GitLab", "Задачи", ["tasks.write"]],
  ["jira", "Jira", "Задачи", ["tasks.write"]],
  ["hubspot", "HubSpot", "CRM", ["crm.write"]],
];
const fullCatalogue = CATALOGUE.map(([key, title, group, capabilities]) => ({
  key,
  title,
  group,
  capabilities: [...capabilities],
  connected: key === "google-mail" || key === "slack",
  connected_at: key === "google-mail" ? "2026-07-05T12:00:00Z" : key === "slack" ? "2026-06-07T12:00:00Z" : null,
  broken: key === "slack",
}));

const connectorsCatalogue = reply("GET", "/v1/connectors", 200, { items: fullCatalogue },
  "карточки каталога черновик показывает по ключам провайдеров в окружении; на стенде их нет");

export const LEO_CABINET_STATES: readonly State[] = [
  cab("populated", (t) => inCabinet(t, 'text="Gmail"'), { scope: "full" }),
  cab("loading", (t) => inCabinet(t, ".rise svg.spin"), {
    overrides: [hold("GET", "/v1/personalization"), hold("GET", "/v1/connectors"), hold("GET", SETTINGS), hold("GET", "/v1/errands")],
  }),
  cab("model-select", () => '[role=option]:has-text("Mistral • Large 3")', {
    act: async (page, { t }) => button(page, t("leo:leo.modelLabel")).click(),
  }),
  // Подпись «Сохраняем…» стоит, пока идёт запрос, только у пользовательских
  // инструкций; у остальных полей её держит таймер паузы ввода (800 мс, потом
  // «Сохранено» на 2 с), и кадр зависел бы от момента снимка.
  cab("personalization-saving", (t) => inCabinet(t, `:text(${JSON.stringify(t("leo:leo.saving"))})`), {
    reveal: true,
    overrides: [hold("PUT", "/v1/personalization")],
    act: async (page, { t }) => {
      const sent = page.waitForRequest((request) => request.method() === "PUT" && new URL(request.url()).pathname === "/v1/personalization");
      const field = page.getByLabel(t("leo:leo.instructionsLabel"), { exact: true });
      await field.fill("Сначала вывод, потом детали.");
      await sent;
      // Фокус снимаем: сглаживание тени фокуса на скруглённых углах поля
      // от прогона к прогону расходится на единицы яркости.
      await field.evaluate((element) => (element as HTMLElement).blur());
    },
  }),
  block("connectors", (t) => t("leo:leo.broken")),
  block("connectors-available", (t) => t("leo:leo.connectOne"), { overrides: [connectorsCatalogue] }),
  block("connector-connecting", (t) => t("leo:leo.connectOne"), {
    overrides: [connectorsCatalogue, hold("POST", "/v1/connectors/session")],
    act: async (page, { t }) => button(page, t("leo:leo.connectOne")).first().click(),
  }),
  cab("connector-connect-failed", (t) => withText("[role=alert]", t("leo:leo.connectFailed")), {
    expectsAlert: true,
    overrides: [connectorsCatalogue, reply("POST", "/v1/connectors/session", 503, { detail: { code: "nango_not_configured" } },
      "подключение идёт через Nango; у стенда его нет")],
    act: async (page, { t }) => button(page, t("leo:leo.connectOne")).first().click(),
  }),
  cab("connector-disconnect-confirm", (t) => dialog(t("leo:leo.disconnectTitle")), {
    act: async (page, { t }) => button(page, t("leo:leo.disconnect")).first().click(),
  }),
  block("initiative", (t) => t("leo:leo.kindNeedsActive")),
  block("initiative-active", (t) => t("leo:leo.levelHint.active"), {
    overrides: [reply("PUT", SETTINGS, 200, settings({ level: "active" }), SAVED)],
    act: async (page, { t }) => button(page, t("leo:leo.level.active")).click(),
  }),
  block("initiative-off", (t) => t("leo:leo.levelHint.off"), {
    overrides: [reply("PUT", SETTINGS, 200, settings({ level: "off" }), SAVED)],
    act: async (page, { t }) => button(page, t("leo:leo.level.off")).click(),
  }),
  cab("quiet-hours-off", (t) => `input[type=time][aria-label=${JSON.stringify(t("leo:leo.quietFrom"))}]:disabled`, {
    reveal: true,
    overrides: [reply("PUT", SETTINGS, 200, settings({ quiet_enabled: false }), SAVED)],
    act: async (page, { t }) => page.getByLabel(t("leo:leo.quietHours"), { exact: true }).click(),
  }),
  block("mail-watches", () => "olga.kim@example.com"),
  block("push", () => "Chrome · macOS"),
  block("memory", (t) => t("leo:leo.memoryEnabledHint")),
  block("memory-off", (t) => t("leo:leo.memoryOffHint"), {
    overrides: [{ method: "GET", path: "/v1/auth/me", reason: "у засеянной персоны память включена", respond: { merge: { memory_enabled: false } } }],
  }),
  block("errands", () => "Gmail отклонил отправку: доступ истёк"),
  block("errands.empty", (t) => t("leo:leo.errandsEmpty"), {
    overrides: [reply("GET", "/v1/errands", 200, { items: [] }, "у засеянной персоны есть поручения")],
  }),
  cab("errand-cancel-confirm", (t) => dialog(t("leo:leo.errandCancelTitle")), {
    act: async (page, { t }) => button(page, t("leo:leo.errandCancel")).first().click(),
  }),
  block("capabilities", (t) => t("leo:leo.capability.leo_connector_search_enabled")),
  {
    // Вкладка только для платных: Free попадает на «Общие».
    id: "leo.cab.free-redirect",
    fixture: "account/cabinet-general",
    url: "/app/cabinet/leo",
    scope: "single",
    marker: (t) => inCabinet(t, withText("*", t("account:cab.appearance"))),
  },
];
