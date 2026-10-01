// Шаблоны заметок и интеграции встреч (шаг 4): списки, редактор шаблона и его
// отказы, карточки интеграций, отказы подключения, тосты возврата из OAuth.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { ALERT, STATUS } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const TEMPLATES = "/v1/me/templates";
const INTEGRATIONS = "/v1/me/integrations";
const CONNECT = "/v1/me/integrations/{type}/connect";

function template(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.templates.${id}`, fixture: "meetings/templates", scope: "single", marker, ...extra };
}

function integration(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.integrations.${id}`, fixture: "meetings/integrations", scope: "single", marker, ...extra };
}

/** Новый шаблон с названием: автосохранение уходит сразу. */
async function nameNewTemplate(page: Page, { t }: StateContext): Promise<void> {
  await page.getByLabel(t("meetings:meet.templates.nameLabel")).fill("Разбор инцидента");
}

const saveRefused = (id: string, status: number, body: JsonValue, text: (t: Translate) => string): State =>
  template(`editor-save-error-${id}`, (t) => exactText(text(t)), {
    url: "/app/templates?new=1",
    overrides: [
      status >= 500
        ? serverError("POST", TEMPLATES)
        : reply("POST", TEMPLATES, status, body, "отказ сохранения шаблона; ответ — api/me_templates.py черновика"),
    ],
    act: nameNewTemplate,
  });

/** Карточка Zapier: ввод адреса и «Подключить». */
async function connectZapier(page: Page, { t }: StateContext): Promise<void> {
  const card = page.getByText("Zapier", { exact: true }).locator("xpath=ancestor::div[.//button][1]");
  await card.locator("input").first().fill("https://hooks.zapier.com/hooks/catch/1/parity");
  await card.getByRole("button", { name: t("meetings:meet.integrations.connect"), exact: true }).click();
}

/** Все девять интеграций не подключены; у Notion в бою настроен OAuth. */
const INTEGRATION_TYPES = ["slack", "zapier", "notion", "hubspot", "attio", "affinity", "google_drive", "dropbox", "yandex_disk"];
const notionOauthReady: JsonValue = INTEGRATION_TYPES.map((type) => ({
  type,
  status: "disconnected",
  accountLabel: null,
  mapping: { pushNotes: true, pushActionItems: true, target: null },
  oauthAvailable: type === "notion",
  accessGranted: null,
}));

const connectRefused = (id: string, status: number, text: (t: Translate) => string): State =>
  integration(`connect-error-${id}`, (t) => exactText(text(t)), {
    overrides: [
      status === 500
        ? serverError("POST", CONNECT)
        : reply("POST", CONNECT, status, { detail: status === 502 ? "upstream_rejected" : "invalid_target" },
          "отказ подключения; провайдеров на стенде нет"),
    ],
    act: connectZapier,
  });

export const MEETINGS_SETUP_STATES: readonly State[] = [
  template("populated", () => 'text="1:1 с руководителем"', { scope: "full" }),
  template("loading", () => "svg.spin", { overrides: [hold("GET", TEMPLATES)] }),
  template("empty", (t) => exactText(t("meetings:meet.templates.emptyTitle")), {
    overrides: [reply("GET", TEMPLATES, 200, [], "встроенные шаблоны приходят всегда; пустой список — это ошибка загрузки")],
  }),
  template("editor-new", (t) => withText("h1", t("meetings:meet.templates.new")), { url: "/app/templates?new=1" }),
  template("editor-edit", (t) => withText("h1", t("meetings:meet.templates.editTitle")), {
    act: async (page, { t }) => page.getByRole("button", { name: t("meetings:meet.templates.edit") }).first().click(),
  }),
  template("editor-copy-builtin", (t) => withText("h1", t("meetings:meet.templates.new")), {
    act: async (page, { t }) => page.getByRole("button", { name: t("meetings:meet.templates.customize") }).first().click(),
  }),
  saveRefused("limit", 422, { detail: "too_many_templates" }, (t) => t("meetings:meet.templates.errLimit")),
  saveRefused("builtin", 422, { detail: "builtin_readonly" }, (t) => t("meetings:meet.templates.errBuiltin")),
  saveRefused("generic", 500, null, (t) => t("meetings:meet.templates.saveFailed")),
  template("delete-error", alert((t) => t("meetings:meet.templates.deleteFailed")), {
    expectsAlert: true,
    overrides: [serverError("DELETE", `${TEMPLATES}/{id}`)],
    act: async (page, { t }) => page.getByRole("button", { name: t("common:actions.delete") }).first().click(),
  }),
  integration("populated", () => 'text="Whisperer Workspace"', { scope: "full" }),
  { id: "meetings.integrations.paywall", fixture: "meetings/integrations-free", scope: "full", marker: (t) => exactText(t("common:premium.title")) },
  integration("loading", () => "main svg.spin", { overrides: [hold("GET", INTEGRATIONS)] }),
  integration("disconnected", (t) => withText("button", t("meetings:meet.integrations.connect")), {
    overrides: [reply("GET", INTEGRATIONS, 200, [], "ни одной интеграции: ответ при ошибке загрузки выглядит так же")],
  }),
  integration("card-oauth", (t) => withText("button", t("meetings:meet.integrations.oauthConnect", { provider: "Notion" })), {
    overrides: [reply("GET", INTEGRATIONS, 200, notionOauthReady, "OAuth Notion настроен ключами провайдера, которых на стенде нет")],
  }),
  integration("storage-waiting", (t) => exactText(t("meetings:meet.integrations.storage.waiting")), {
    overrides: [
      reply("GET", "/v1/me/integrations/{type}/oauth/authorize", 200, { url: "https://connect.nango.dev/parity" },
        "ссылку на экран доступа выдаёт Nango, которого на стенде нет"),
      hold("POST", CONNECT),
    ],
    act: async (page, { t }) =>
      page.getByRole("button", { name: t("meetings:meet.integrations.oauthConnect", { provider: "Google Drive" }) }).click(),
  }),
  connectRefused("validation", 422, (t) => t("meetings:meet.integrations.error.validation")),
  connectRefused("upstream", 502, (t) => t("meetings:meet.integrations.error.upstream")),
  connectRefused("generic", 500, (t) => t("meetings:meet.integrations.error.generic")),
  integration("oauth-toast-ok", (t) => withText(STATUS, t("meetings:meet.integrations.oauth.ok", { provider: "Notion" })), {
    url: "/app/settings/integrations?oauth=notion_ok",
  }),
  integration("oauth-toast-attio", (t) => withText(STATUS, t("meetings:meet.integrations.oauth.attioOk")), {
    url: "/app/settings/integrations?oauth=attio_ok",
  }),
  integration("oauth-toast-error", (t) => withText(ALERT, t("meetings:meet.integrations.oauth.err", { provider: "Notion" })), {
    url: "/app/settings/integrations?oauth=notion_err",
    expectsAlert: true,
  }),
];
