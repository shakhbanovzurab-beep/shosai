// Промпты и скиллы (шаг 5): библиотека промптов и окно скиллов (каталог, свой
// репозиторий, свои). Редактор и тестовый прогон — prompts-editor.ts.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const PROMPTS = "/v1/admin/prompts";
const SEARCH = "/v1/me/skills/search";
const CATALOG_REASON = "каталог скиллов — внешние skills.sh и GitHub; у стенда нет сети";

const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
export const skillsDialog = (t: Translate): string => dialog(t("leo:skills.title"));
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> => page.getByRole("button", { name, exact: true });

function list(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `prompts.${id}`, fixture: "prompts/list", scope: "single", marker, ...extra };
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
];
