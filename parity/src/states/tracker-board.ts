// Доска трекера (шаг 6): колонки и карточки, фильтры, меню задачи и колонки,
// окна задачи и колонки, отказ удалить колонку с задачами, синхронизация с Jira.
//
// Статус связи с Jira черновик берёт из базы (обе связи засеяны); сайты и
// проекты Atlassian, привязка и синхронизация идут в сеть — их ответы синтетика.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { withText, type Translate } from "../i18n/texts.ts";
import { hold, reply } from "./overrides.ts";
import type { Override, State, StateContext } from "./types.ts";

const BOARD = "/v1/me/tracker/projects/{id}/board";
const JIRA_STATUS = "/v1/me/jira/links/{id}";
const ATLASSIAN_REASON = "сайты и проекты отдаёт Atlassian; у стенда нет сети и токенов";

const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });
const card = (title: string): string => `button.trk-card[aria-label=${JSON.stringify(title)}]`;

function board(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `tracker.board.${id}`, fixture: "tracker/board", scope: "single", marker, ...extra };
}

function jira(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `tracker.jira.${id}`, fixture: "tracker/board", scope: "single", marker, ...extra };
}

async function columnMenu(page: Page, { t }: StateContext): Promise<void> {
  await page.getByTitle(t("tracker:tracker.actions.columnMenu"), { exact: true }).first().click();
}

async function taskMenu(page: Page): Promise<void> {
  await page.locator(card("Открыть тестовый доступ к API")).click({ button: "right" });
}

/** Чип Jira в шапке доски: ведёт к окну синхронизации. */
async function openJira(page: Page, { t }: StateContext): Promise<void> {
  await page.locator(`button[title=${JSON.stringify(t("tracker:tracker.jira.chipLinked", { key: "ACME" }))}], button:text-is("Jira")`).click();
  await page.locator(dialog(t("tracker:tracker.jira.title"))).waitFor();
}

const status = (patch: { readonly [key: string]: JsonValue }, reason: string): Override =>
  ({ method: "GET", path: JIRA_STATUS, reason, respond: { merge: patch } });

const NOT_LINKED = { project_key: null, project_name: null, site_url: null, last_sync_at: null, last_error: null, live: false };

export const TRACKER_BOARD_STATES: readonly State[] = [
  board("populated", () => card("Открыть тестовый доступ к API"), { scope: "full" }),
  board("loading", () => "svg.spin", { overrides: [hold("GET", BOARD)] }),
  board("filtered", () => card("Настроить вход через Azure AD"), {
    act: async (page, { t }) => page.getByLabel(t("tracker:tracker.board.search"), { exact: true }).fill("вход"),
  }),
  board("filter-priority", () => card("Открыть тестовый доступ к API"), {
    act: async (page, { t }) => {
      await page.getByRole("combobox").filter({ hasText: t("tracker:tracker.board.allPriorities") }).click();
      await page.getByRole("option", { name: t("tracker:tracker.priority.urgent"), exact: true }).click();
    },
  }),
  board("task-menu", (t) => withText("div.pop", t("tracker:tracker.priority.urgent")), { act: taskMenu }),
  board("column-menu", (t) => withText("div.pop", t("tracker:tracker.actions.deleteColumn")), { act: columnMenu }),
  board("task-modal.new", (t) => dialog(t("tracker:tracker.task.newTitle")), {
    act: async (page, { t }) => page.getByTitle(t("tracker:tracker.actions.addTask"), { exact: true }).first().click(),
  }),
  board("task-modal.edit", (t) => withText(dialog(t("tracker:tracker.task.editTitle")), "Ключи и песочница для команды Acme"), {
    act: async (page) => page.locator(card("Открыть тестовый доступ к API")).click(),
  }),
  board("pending", () => '.trk-card[data-pending="true"]', {
    overrides: [hold("POST", "/v1/me/tracker/projects/{id}/tasks")],
    act: async (page, { t }) => {
      await page.getByTitle(t("tracker:tracker.actions.addTask"), { exact: true }).first().click();
      const modal = page.locator(dialog(t("tracker:tracker.task.newTitle")));
      await modal.getByLabel(t("tracker:tracker.task.title"), { exact: true }).fill("Провести демо для отдела продаж");
      await modal.getByRole("button", { name: t("tracker:tracker.actions.create"), exact: true }).click();
    },
  }),
  board("status-modal.new", (t) => dialog(t("tracker:tracker.column.newTitle")), {
    act: async (page, { t }) => button(page, t("tracker:tracker.actions.addColumn")).click(),
  }),
  board("status-modal.edit", (t) => dialog(t("tracker:tracker.column.editTitle")), {
    act: async (page, context) => {
      await columnMenu(page, context);
      await button(page, context.t("tracker:tracker.actions.editColumn")).click();
    },
  }),
  board("delete-confirm", (t) => withText(dialog(t("tracker:tracker.actions.delete")), "Открыть тестовый доступ к API"), {
    act: async (page, { t }) => {
      await taskMenu(page);
      await button(page, t("tracker:tracker.actions.delete")).click();
    },
  }),
  board("column-delete-error", (t) => withText("[role=alert]", t("tracker:tracker.errors.columnDelete")), {
    expectsAlert: true,
    act: async (page, context) => {
      await columnMenu(page, context);
      await button(page, context.t("tracker:tracker.actions.deleteColumn")).click();
    },
  }),

  jira("chip.failing", (t) => `button[title=${JSON.stringify(t("tracker:tracker.jira.chipError", { key: "PORT" }))}]`, { fixture: "tracker/board-portal" }),
  jira("chip.unlinked", () => 'button:text-is("Jira")', {
    overrides: [status(NOT_LINKED, "засеянная доска связана с проектом Jira")],
  }),
  jira("modal.linked", (t) => withText(dialog(t("tracker:tracker.jira.title")), t("tracker:tracker.jira.live")), { act: openJira }),
  {
    id: "tracker.jira.modal.failing",
    fixture: "tracker/board-portal",
    scope: "single",
    marker: (t) => withText(dialog(t("tracker:tracker.jira.title")), "503: Service Unavailable"),
    act: async (page, { t }) => {
      await page.locator(`button[title=${JSON.stringify(t("tracker:tracker.jira.chipError", { key: "PORT" }))}]`).click();
    },
  },
  jira("modal.connect", (t) => withText(dialog(t("tracker:tracker.jira.title")), t("tracker:tracker.jira.connectHint")), {
    overrides: [reply("GET", JIRA_STATUS, 200, { connected: false, account: null, ...NOT_LINKED }, "у засеянной персоны Atlassian подключён")],
    act: openJira,
  }),
  jira("modal.choose", (t) => withText(dialog(t("tracker:tracker.jira.title")), t("tracker:tracker.jira.connectedAs", { account: "Мария Соколова" })), {
    overrides: [
      status(NOT_LINKED, "засеянная доска уже связана с проектом Jira"),
      reply("GET", "/v1/me/jira/sites", 200, [{ cloud_id: "parity-cloud", name: "acme", url: "https://acme.atlassian.net" }], ATLASSIAN_REASON),
      reply("GET", "/v1/me/jira/projects", 200, [
        { id: "10000", key: "ACME", name: "Acme Implementation" },
        { id: "10002", key: "OPS", name: "Operations" },
      ], ATLASSIAN_REASON),
    ],
    act: openJira,
  }),
  jira("toast.synced", (t) => withText("[role=status]", t("tracker:tracker.jira.syncResult", { pulled: 3, pushed: 1 })), {
    overrides: [reply("POST", "/v1/me/jira/links/{id}/sync", 200, { pulled: 3, pushed: 1, skipped: 0, failed: 0, errors: [] }, ATLASSIAN_REASON)],
    act: async (page, context) => {
      await openJira(page, context);
      await button(page, context.t("tracker:tracker.jira.syncNow")).click();
    },
  }),
];
