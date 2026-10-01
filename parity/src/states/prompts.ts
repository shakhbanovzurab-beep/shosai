// Промпты и скиллы (шаг 5): библиотека промптов, окно скиллов (каталог, свой
// репозиторий, свои), редактор и тестовый прогон. Прогон — поток SSE без имён
// событий в формате OpenAI; идущий прогон — открытый поток.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, openStream, reply, serverError, stream, type StreamEvent } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const PROMPTS = "/v1/admin/prompts";
const SEARCH = "/v1/me/skills/search";
const TEST_RUN = "/v1/admin/prompts/{id}/test";
const CATALOG_REASON = "каталог скиллов — внешние skills.sh и GitHub; у стенда нет сети";
const RUN_REASON = "прогон отвечает моделью этой роли; на стенде её нет";

const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
const skillsDialog = (t: Translate): string => dialog(t("leo:skills.title"));
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });

function list(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `prompts.${id}`, fixture: "prompts/list", scope: "single", marker, ...extra };
}

function editor(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `prompts.${id}`, fixture: "prompts/editor", scope: "single", marker, ...extra };
}

async function openSkills(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("leo:skills.title")).click();
  await page.locator(skillsDialog(t)).waitFor();
}

async function searchHub(page: Page, context: StateContext): Promise<void> {
  await openSkills(page, context);
  await page.getByPlaceholder(context.t("leo:skills.searchPlaceholder"), { exact: true }).fill("review");
}

async function discoverRepo(page: Page, context: StateContext): Promise<void> {
  await openSkills(page, context);
  await button(page, context.t("leo:skills.tabRepo")).click();
  await page.getByPlaceholder(context.t("leo:skills.repoPlaceholder"), { exact: true }).fill("acme/skills");
  await button(page, context.t("leo:skills.repoFind")).click();
}

const HUB_HITS = [
  { slug: "code-review", repo: "acme/skills", installs: 1840 },
  { slug: "review-checklist", repo: "vercel-labs/agent-skills", installs: 12_400 },
  { slug: "pr-review", repo: "anthropics/skills", installs: 8_310 },
];

/** Файл импорта: разбор идёт в браузере, неподходящий файл до сервера не доходит. */
async function importFile(page: Page, t: Translate, name: string, text: string): Promise<void> {
  await page.locator(`input[aria-label=${JSON.stringify(t("prompts:prompts.import"))}]`)
    .setInputFiles({ name, mimeType: "application/json", buffer: Buffer.from(text) });
}

const chunk = (content: string): StreamEvent => ({ event: "", data: { choices: [{ delta: { content } }] } });
const RUN_TEXT = ["Идея: ", "пройти по списку один раз ", "и копить сумму в переменной.\n\n", "Сложность — O(n)."];

async function run(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("prompts:promptEditor.run")).click();
}

export const PROMPTS_STATES: readonly State[] = [
  list("list.populated", () => 'text="Черновик ответов (старый)"', { scope: "full" }),
  list("list.loading", () => "svg.spin", { overrides: [hold("GET", PROMPTS)] }),
  { id: "prompts.list.empty", fixture: "prompts/empty", scope: "single", marker: (t) => exactText(t("prompts:prompts.empty")) },
  list("list.filter.coding", () => 'text="Собеседование: Python"', {
    act: async (page, { t }) => button(page, t("common:roles.coding")).click(),
  }),
  list("list.role-tooltip", (t) => withText("[role=tooltip]", t("prompts:prompts.tabAllHelp")), {
    keepPointer: true,
    act: async (page, { t }) => button(page, t("prompts:prompts.tabAll")).hover(),
  }),
  list("list.row-hover", () => 'tr:has-text("Разбор скриншотов")', {
    keepPointer: true,
    act: async (page) => page.locator('tr:has-text("Разбор скриншотов")').hover(),
  }),
  list("kpi.empty-runs", (t) => exactText(t("prompts:prompts.kpiRunsEmpty")), {
    overrides: [reply("GET", `${PROMPTS}/stats`, 200,
      { runs_30d: 0, latency_p50_ms: null, cost_today: "0.00", cost_today_currency: "RUB", tokens_30d: 0 },
      "у засеянной персоны есть расходы на модели")],
  }),
  list("import.bad-file", (t) => withText("[role=alert]", t("prompts:prompts.importBadFile")), {
    expectsAlert: true,
    act: async (page, { t }) => importFile(page, t, "заметки.txt", "это не JSON"),
  }),
  list("import.empty", (t) => withText("[role=alert]", t("prompts:prompts.importEmpty")), {
    expectsAlert: true,
    act: async (page, { t }) => importFile(page, t, "prompts.json", "[]"),
  }),
  list("delete-confirm", (t) => dialog(t("prompts:prompts.deleteTitle")), {
    act: async (page, { t }) => button(page, t("prompts:prompts.deleteTitle")).first().click(),
  }),
  list("skills.hub-idle", (t) => `${skillsDialog(t)} >> ${exactText(t("leo:skills.hubTitle"))}`, { act: openSkills }),
  list("skills.hub-searching", (t) => `${skillsDialog(t)} >> ${exactText(t("leo:skills.searching"))}`, {
    overrides: [hold("GET", SEARCH)],
    act: searchHub,
  }),
  list("skills.hub-results", () => 'text="review-checklist"', {
    overrides: [reply("GET", SEARCH, 200, HUB_HITS, CATALOG_REASON)],
    act: searchHub,
  }),
  list("skills.hub-nothing", (t) => `${skillsDialog(t)} >> ${exactText(t("leo:skills.nothingFound"))}`, {
    overrides: [reply("GET", SEARCH, 200, [], CATALOG_REASON)],
    act: searchHub,
  }),
  list("skills.install-error", (t) => withText("[role=alert]", t("leo:skills.errors.github_unavailable")), {
    expectsAlert: true,
    overrides: [
      reply("GET", SEARCH, 200, HUB_HITS, CATALOG_REASON),
      reply("POST", "/v1/me/skills", 502, { detail: "github_unavailable" }, CATALOG_REASON),
    ],
    act: async (page, context) => {
      await searchHub(page, context);
      // «code-review» уже в библиотеке: первая кнопка установки — у «review-checklist».
      await button(page, context.t("leo:skills.install")).first().click();
    },
  }),
  list("skills.repo-idle", (t) => `${skillsDialog(t)} >> ${exactText(t("leo:skills.repoTitle"))}`, {
    act: async (page, context) => {
      await openSkills(page, context);
      await button(page, context.t("leo:skills.tabRepo")).click();
    },
  }),
  list("skills.repo-results", (t) => `${skillsDialog(t)} >> ${exactText(t("leo:skills.repoRoot"))}`, {
    overrides: [reply("GET", "/v1/me/skills/discover", 200, {
      repo: "acme/skills",
      ref: "3f2c9a1e0b7d4c5a",
      skills: [
        { slug: "code-review", description: "Чек-лист code-review: шаги и критерии", skill_path: "skills/code-review", truncated: false, installed: true },
        { slug: "release-notes", description: "Заметки к релизу по списку изменений", skill_path: "skills/release-notes", truncated: false, installed: false },
        { slug: "onboarding", description: "Онбординг нового сотрудника", skill_path: "", truncated: false, installed: false },
      ],
    }, CATALOG_REASON)],
    act: discoverRepo,
  }),
  list("skills.repo-error", (t) => withText(`${skillsDialog(t)} [role=alert]`, t("leo:skills.errors.repo_not_found")), {
    expectsAlert: true,
    overrides: [reply("GET", "/v1/me/skills/discover", 404, { detail: "repo_not_found" }, CATALOG_REASON)],
    act: discoverRepo,
  }),
  list("skills.mine-populated", () => 'text="sql-tuning"', {
    act: async (page, context) => {
      await openSkills(page, context);
      await button(page, context.t("leo:skills.tabMine", { count: 3 })).click();
    },
  }),
  {
    id: "prompts.skills.mine-empty",
    fixture: "prompts/empty",
    scope: "single",
    marker: (t) => `${skillsDialog(t)} >> ${exactText(t("leo:skills.empty"))}`,
    act: async (page, context) => {
      await openSkills(page, context);
      await button(page, context.t("leo:skills.tabMine", { count: 0 })).click();
    },
  },

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
