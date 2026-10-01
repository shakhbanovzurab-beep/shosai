// Редактор промпта (шаг 5): переменные, подключённые скиллы и тестовый прогон.
// Прогон — поток SSE без имён событий в формате OpenAI; идущий прогон — открытый
// поток.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { openStream, reply, serverError, stream, type StreamEvent } from "./overrides.ts";
import { skillsDialog } from "./prompts.ts";
import type { State, StateContext } from "./types.ts";

const TEST_RUN = "/v1/admin/prompts/{id}/test";
const RUN_REASON = "прогон отвечает моделью этой роли; на стенде её нет";

const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });

function editor(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `prompts.${id}`, fixture: "prompts/editor", scope: "single", marker, ...extra };
}

const chunk = (content: string): StreamEvent => ({ event: "", data: { choices: [{ delta: { content } }] } });
const RUN_TEXT = ["Идея: ", "пройти по списку один раз ", "и копить сумму в переменной.\n\n", "Сложность — O(n)."];

async function run(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("prompts:promptEditor.run")).click();
}

export const PROMPTS_EDITOR_STATES: readonly State[] = [
  editor("editor.populated", (t) => exactText(t("leo:skills.replaceNote")), { scope: "full" }),
  {
    id: "prompts.editor.variables",
    fixture: "prompts/editor-vars",
    scope: "single",
    marker: (t) => exactText(t("leo:skills.promptEmpty")),
  },
  editor("editor.skills-full", (t) => exactText(t("leo:skills.maxPerPrompt")), {
    overrides: [{
      method: "GET",
      path: "/v1/admin/prompts/{id}",
      reason: "к засеянному промпту подключены два скилла",
      respond: { merge: { skills: [
        { skill_id: "00000000-0000-4000-8000-000000000011", slug: "code-review", description: "Чек-лист code-review: шаги и критерии", mode: "append" },
        { skill_id: "00000000-0000-4000-8000-000000000012", slug: "star-method", description: "Чек-лист star-method: шаги и критерии", mode: "replace" },
        { skill_id: "00000000-0000-4000-8000-000000000013", slug: "sql-tuning", description: "Чек-лист sql-tuning: шаги и критерии", mode: "append" },
      ] } },
    }],
  }),
  editor("editor.skill-picker", (t) => `${skillsDialog(t)} >> text="sql-tuning"`, {
    act: async (page, { t }) => {
      await button(page, t("leo:skills.attach")).click();
      await button(page, t("leo:skills.tabMine", { count: 3 })).click();
    },
  }),
  editor("editor.skills-error", (t) => withText("[role=alert]", t("leo:skills.errors.generic")), {
    expectsAlert: true,
    overrides: [serverError("PUT", "/v1/admin/prompts/{id}/skills")],
    act: async (page, { t }) => page.getByRole("button", { name: t("leo:skills.detach"), exact: true }).first().click(),
  }),
  editor("editor.save-error", (t) => withText("[role=alert]", t("prompts:promptEditor.saveError")), {
    expectsAlert: true,
    overrides: [serverError("PATCH", "/v1/admin/prompts/{id}")],
    act: async (page, { t }) => {
      const sent = page.waitForRequest((request) => request.method() === "PATCH");
      const name = page.getByLabel(t("prompts:promptEditor.nameLabel"), { exact: true });
      await name.fill("Собеседование: Python и SQL");
      await sent;
      // Фокус поля после ошибки у черновика то остаётся, то нет: снимаем его.
      await name.evaluate((element) => (element as HTMLElement).blur());
    },
  }),
  editor("testrun.streaming", (t) => `button:disabled:has-text(${JSON.stringify(t("prompts:promptEditor.streaming"))})`, {
    overrides: [openStream("POST", TEST_RUN, RUN_TEXT.slice(0, 2).map(chunk), RUN_REASON)],
    act: run,
  }),
  editor("testrun.done", () => 'text=/Сложность — O\\(n\\)\\./', {
    overrides: [stream("POST", TEST_RUN, [...RUN_TEXT.map(chunk), { event: "", data: "[DONE]" }], RUN_REASON)],
    act: run,
  }),
  editor("testrun.error", (t) => withText("[role=alert]", t("prompts:promptEditor.errForbidden")), {
    expectsAlert: true,
    overrides: [reply("POST", TEST_RUN, 403, { detail: "forbidden" }, "прогон чужого промпта; засеяны только свои")],
    act: run,
  }),
];
