// Трекер (шаг 6): список проектов — загрузка, пусто, архив, меню карточки, окна
// проекта и подтверждение удаления. Доска и Jira — tracker-board.ts.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const PROJECTS = "/v1/me/tracker/projects";

const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });

function projects(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `tracker.${id}`, fixture: "tracker/projects", scope: "single", marker, ...extra };
}

async function cardMenu(page: Page, { t }: StateContext): Promise<void> {
  await page.locator('.trk-proj-card:has-text("Внедрение Acme")').getByTitle(t("common:actions.more"), { exact: true }).click();
}

const menuItem = (item: (t: Translate) => string) => async (page: Page, context: StateContext): Promise<void> => {
  await cardMenu(page, context);
  await button(page, item(context.t)).click();
};

export const TRACKER_STATES: readonly State[] = [
  projects("projects.populated", () => 'text="Внедрение Acme"', { scope: "full" }),
  projects("projects.loading", () => "svg.spin", { overrides: [hold("GET", PROJECTS)] }),
  {
    id: "tracker.projects.empty",
    fixture: "tracker/empty",
    scope: "single",
    marker: (t) => exactText(t("tracker:tracker.project.emptyTitle")),
  },
  projects("projects.archived", (t) => exactText(t("tracker:tracker.project.emptyTitle")), {
    act: async (page, { t }) => button(page, t("tracker:tracker.project.showArchived")).click(),
  }),
  projects("projects.menu", (t) => withText("div.pop", t("tracker:tracker.project.archive")), { act: cardMenu }),
  projects("project.modal.new", (t) => dialog(t("tracker:tracker.project.newTitle")), {
    act: async (page, { t }) => button(page, t("tracker:tracker.project.new")).click(),
  }),
  projects("projects.pending-card", () => '.trk-proj-card[data-pending="true"]', {
    overrides: [hold("POST", PROJECTS)],
    act: async (page, { t }) => {
      await button(page, t("tracker:tracker.project.new")).click();
      const modal = page.locator(dialog(t("tracker:tracker.project.newTitle")));
      await modal.getByLabel(t("tracker:tracker.project.name"), { exact: true }).fill("Онбординг партнёров");
      await modal.getByLabel(t("tracker:tracker.project.key"), { exact: true }).fill("ONB");
      await modal.getByRole("button", { name: t("tracker:tracker.actions.create"), exact: true }).click();
    },
  }),
  projects("project.modal.edit", (t) => dialog(t("tracker:tracker.project.editTitle")), {
    act: menuItem((t) => t("tracker:tracker.actions.edit")),
  }),
  projects("project.delete-confirm", (t) => withText(dialog(t("tracker:tracker.actions.delete")), "Внедрение Acme"), {
    act: menuItem((t) => t("tracker:tracker.actions.delete")),
  }),
  projects("projects.action-error", (t) => withText("[role=alert]", t("tracker:tracker.actionError")), {
    expectsAlert: true,
    overrides: [
      serverError("PATCH", `${PROJECTS}/{id}`),
      // Откат возвращает карточку под указатель, и наведение заранее грузит доску соседней.
      { method: "GET", path: `${PROJECTS}/{id}/board`, respond: "hold", reason: "предзагрузка доски по наведению на экран не влияет" },
    ],
    act: menuItem((t) => t("tracker:tracker.project.archive")),
  }),
];
