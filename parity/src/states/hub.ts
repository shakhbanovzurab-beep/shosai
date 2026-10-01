// Хабы (шаг 5): список дел, меню карточки, архивация с пульсом, создание;
// страница дела — цель, что горит, материалы, лента и сводка после встречи.
// Подсказка Leo «только по этому хабу» — на странице дела.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { openPanel } from "./leo-common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const HUBS = "/v1/hubs";
const HUB = "/v1/hubs/{id}";

const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });

function list(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `hub.${id}`, fixture: "hub/list", scope: "single", marker, ...extra };
}

function detail(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `hub.detail.${id}`, fixture: "hub/acme", scope: "single", marker, ...extra };
}

async function cardMenu(page: Page, t: Translate, hub: string): Promise<void> {
  await page.locator(`.hub-card:has-text(${JSON.stringify(hub)})`).getByRole("button", { name: t("hub:hub.row.actions"), exact: true }).click();
}

const menuItem = (item: (t: Translate) => string, hub = "Acme") => async (page: Page, { t }: StateContext): Promise<void> => {
  await cardMenu(page, t, hub);
  await button(page, item(t)).click();
};

async function openPicker(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("hub:hub.materials.add")).click();
  await page.locator(dialog(t("hub:hub.materials.add"))).waitFor();
}

async function searchMaterial(page: Page, context: StateContext, query: string): Promise<void> {
  await openPicker(page, context);
  await page.locator(dialog(context.t("hub:hub.materials.add")))
    .getByLabel(context.t("hub:hub.materials.searchLabel"), { exact: true }).fill(query);
}

export const HUB_STATES: readonly State[] = [
  list("list.populated", (t) => exactText(t("hub:hub.listTitle", { count: 2 })), { scope: "full" }),
  list("list.loading", () => "div.py-16 svg.spin", { overrides: [hold("GET", HUBS)] }),
  list("list.empty", (t) => exactText(t("hub:hub.empty.title")), {
    overrides: [reply("GET", HUBS, 200, { items: [] }, "у засеянной персоны есть дела")],
  }),
  list("list.no-boards", (t) => withText("p", t("hub:hub.noBoardsAtAll")), {
    overrides: [reply("GET", "/v1/me/tracker/projects", 200, [], "у засеянной персоны есть доски")],
  }),
  list("list.all", (t) => withText(".hub-card", t("hub:hub.row.archived")), {
    act: async (page, { t }) => button(page, t("hub:hub.filter.all")).click(),
  }),
  list("card.menu", (t) => withText("div.pop", t("hub:hub.row.boardNotChosen")), {
    act: async (page, { t }) => cardMenu(page, t, "Acme"),
  }),
  list("card.rename", (t) => dialog(t("hub:hub.row.rename")), { act: menuItem((t) => t("hub:hub.row.rename")) }),
  list("card.delete-confirm", (t) => dialog(t("hub:hub.delete.title", { name: "Acme" })), { act: menuItem((t) => t("hub:hub.row.delete")) }),
  list("closing.left", (t) => withText(dialog(t("hub:hub.closing.title", { name: "Acme" })), t("hub:hub.closing.left", { count: 6 })), {
    act: menuItem((t) => t("hub:hub.row.archive")),
  }),
  list("closing.clear", (t) => withText(dialog(t("hub:hub.closing.title", { name: "Северный ветер" })), t("hub:hub.closing.clear")), {
    act: menuItem((t) => t("hub:hub.row.archive"), "Северный ветер"),
  }),
  list("closing.loading", (t) => `${dialog(t("hub:hub.closing.title", { name: "Acme" }))} svg.spin`, {
    overrides: [hold("GET", "/v1/hubs/{id}/pulse")],
    act: menuItem((t) => t("hub:hub.row.archive")),
  }),
  list("create.modal", (t) => dialog(t("hub:hub.create.title")), {
    act: async (page, { t }) => button(page, t("hub:hub.create.submit")).click(),
  }),
  list("create.error", (t) => exactText(t("hub:hub.error.name_taken")), {
    overrides: [reply("POST", HUBS, 409, { detail: "name_taken" }, "имя совпадает с засеянным делом; стенд записи его не создавал")],
    act: async (page, { t }) => {
      await button(page, t("hub:hub.create.submit")).click();
      const create = page.locator(dialog(t("hub:hub.create.title")));
      await create.getByPlaceholder(t("hub:hub.create.placeholder"), { exact: true }).fill("Acme");
      await create.getByRole("button", { name: t("hub:hub.create.submit"), exact: true }).click();
    },
  }),

  detail("populated", (t) => exactText(t("hub:hub.digest.title")), { scope: "full" }),
  detail("loading", () => "svg.spin", { overrides: [hold("GET", HUB)] }),
  detail("blocks-loading", (t) => exactText(t("hub:hub.detail.feed")), {
    overrides: [hold("GET", "/v1/hubs/{id}/feed"), hold("GET", "/v1/hubs/{id}/pulse"), hold("GET", "/v1/hubs/{id}/materials")],
  }),
  detail("gone", (t) => exactText(t("hub:hub.detail.gone")), {
    overrides: [reply("GET", HUB, 404, { detail: "hub_not_found" }, "дело удалено после записи")],
  }),
  detail("feed.empty", (t) => exactText(t("hub:hub.detail.emptyFeed")), {
    overrides: [reply("GET", "/v1/hubs/{id}/feed", 200, { entries: [], facts_total: 0 }, "у засеянного дела есть встречи")],
  }),
  detail("charter.editing", (t) => exactText(t("hub:hub.charter.purposeLabel")), {
    act: async (page, { t }) => button(page, t("hub:hub.charter.edit")).click(),
  }),
  detail("charter.empty", (t) => exactText(t("hub:hub.charter.empty")), {
    overrides: [{ method: "GET", path: HUB, reason: "у засеянного дела есть цель", respond: { merge: { purpose: null, success: null } } }],
  }),
  detail("materials", () => 'text="Смета_пилота_Acme_v2.xlsx"', { reveal: true }),
  detail("feed", (t) => exactText(t("hub:hub.feed.untitled")), { reveal: true }),
  detail("materials.empty", (t) => exactText(t("hub:hub.materials.empty")), {
    reveal: true,
    overrides: [reply("GET", "/v1/hubs/{id}/materials", 200, { items: [] }, "у засеянного дела есть материалы")],
  }),
  detail("material-picker", (t) => `${dialog(t("hub:hub.materials.add"))} >> ${exactText(t("hub:hub.materials.upload"))}`, { act: openPicker }),
  detail("material-results", (t) => `${dialog(t("hub:hub.materials.add"))} >> text="Бюджет 2026.xlsx"`, {
    act: async (page, context) => searchMaterial(page, context, "Бюджет"),
  }),
  detail("material-nothing", (t) => `${dialog(t("hub:hub.materials.add"))} >> ${exactText(t("hub:hub.materials.nothingFound"))}`, {
    overrides: [reply("GET", "/v1/me/search", 200, { query: "Бюджет", total: 0, hits: [], unavailable: [] },
      "поиск по засеянным материалам находит документы")],
    act: async (page, context) => searchMaterial(page, context, "Бюджет"),
  }),
  detail("material-upload-error", (t) => withText("[role=alert]", t("hub:hub.materials.uploadFailed")), {
    expectsAlert: true,
    overrides: [serverError("POST", "/v1/me/storage/upload")],
    act: async (page, context) => {
      await openPicker(page, context);
      await page.locator(`input[type=file][aria-label=${JSON.stringify(context.t("hub:hub.materials.upload"))}]`)
        .setInputFiles({ name: "смета.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.alloc(2048, 1) });
    },
  }),
  { id: "hub.detail.quiet", fixture: "hub/wind", scope: "single", marker: (t) => exactText(t("hub:hub.loops.clear")) },
  {
    id: "leo.panel.hub-scope",
    fixture: "hub/acme",
    scope: "single",
    act: openPanel,
    marker: (t) => exactText(t("leo:leo.scope.hub")),
  },
];
