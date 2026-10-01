// Дашборд админки и «Деньги» (шаг 7): сводка, тревоги, разбивка по измерениям
// со страницами, сортировкой и периодом, онбординг; расходы по провайдерам,
// моделям и ролям. Тексты дашборда вшиты по-русски (находка в инвентаре) —
// только ru; «Деньги» переведены.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { DRILL_DIMENSIONS } from "../recording/visits/admin.ts";
import { button, choose } from "../ui/admin-ui.ts";
import { hold, reply } from "./overrides.ts";
import type { Override, State } from "./types.ts";

const DASHBOARD = "/v1/admin/dashboard";
const DRILL = "/v1/admin/analytics/drill";
const SUMMARY = "/v1/admin/costs/summary";
const RU: readonly string[] = ["ru"];

const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;
/** Записанный ответ с правкой полей. */
export const merged = (method: string, path: string, merge: { readonly [key: string]: JsonValue }, reason: string): Override =>
  ({ method, path, reason, respond: { merge } });

/** Ответ дашборда, как его записал визит admin/dashboard. */
const DASHBOARD_BODY: { readonly [key: string]: JsonValue } = {
  active_sessions_now: 0, users_total: 22, new_users_today: 1, new_users_7d: 1, paid_users: 9, trial_to_paid_pct: 40.9,
  mrr_rub: 22418.57, users_by_tariff: { free: 13, pro_1m: 6, max_1m: 2, start: 1 },
  users_by_status: { active: 20, banned: 1, frozen: 1 }, api_spend_today_rub: 280.61, api_spend_7d_rub: 315.85,
  api_spend_30d_rub: 472.92, tokens_per_min: 904.8, llm_requests_per_min: 0.3, churn_pct: 0,
  ltv_by_tariff: { max: 3490, pro: 1990, start: 790 },
  alerts: [
    { user: "abuser@parity.test", text: "Сжёг 200 000 токенов за час", level: "error" },
    { user: "cheap@parity.test", text: "Резкий рост токенов/мин ×60", level: "warn" },
  ],
};

function dashboard(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.dashboard.${id}`, fixture: "admin/dashboard", scope: "single", languages: RU, marker, ...extra };
}

function costs(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.costs.${id}`, fixture: "admin/costs", scope: "single", marker, ...extra };
}

/** Измерение разбивки из исходного «Модели»; slug — для идентификатора состояния. */
const DIMENSION_SLUGS: Readonly<Record<(typeof DRILL_DIMENSIONS)[number], string>> = {
  "Пользователи": "user",
  "Тарифы": "tariff",
  "Провайдеры": "provider",
  "Роли": "role",
  "Объекты (сессии)": "object",
};

async function pickRange(page: Page): Promise<void> {
  await page.getByLabel("Начало периода", { exact: true }).fill("2026-07-01");
  await page.getByLabel("Конец периода", { exact: true }).fill("2026-07-15");
}

export const ADMIN_DASHBOARD_STATES: readonly State[] = [
  dashboard("populated", text("Онбординг новых пользователей"), { scope: "full" }),
  dashboard("loading", () => "div.p-10 svg.spin", { overrides: [hold("GET", DASHBOARD)] }),
  dashboard("alerts-empty", text("Аномалий расхода за последние сутки не обнаружено."), {
    overrides: [merged("GET", DASHBOARD, { alerts: [] }, "в засеве есть всплески токенов")],
  }),
  // Правка сливает объекты глубоко и пустой словарь не опустошает: ответ целиком.
  dashboard("breakdown-empty", () => 'div:text-is("Нет данных")', {
    overrides: [reply("GET", DASHBOARD, 200, { ...DASHBOARD_BODY, users_by_tariff: {}, users_by_status: {} },
      "у засеянных пользователей есть подписки")],
  }),
  // Всё остальное на странице уже загружено: единственный индикатор — у разбивки.
  dashboard("drill.loading", () => "svg.spin", {
    reveal: true,
    overrides: [hold("GET", DRILL)],
  }),
  dashboard("drill.empty", text("Нет данных за период."), {
    reveal: true,
    overrides: [merged("GET", DRILL, { rows: [], total: 0, has_more: false }, "у засеянных моделей есть расходы")],
  }),
  ...DRILL_DIMENSIONS.map((dimension) => dashboard(`drill.dimension-${DIMENSION_SLUGS[dimension]}`, () =>
    `[role=combobox]:has-text(${JSON.stringify(dimension)})`, {
    reveal: true,
    act: async (page) => choose(page, "Модели", dimension),
  })),
  dashboard("drill.sorted-asc", text("Значение ▲"), {
    reveal: true,
    act: async (page) => page.locator('button[aria-label="Сортировать по значению"]').click(),
  }),
  dashboard("drill.page-2", text("стр. 2"), { reveal: true, act: async (page) => button(page, "Вперёд →").click() }),
  dashboard("drill.date-range", () => 'input[aria-label="Конец периода"][value="2026-07-15"]', { reveal: true, act: pickRange }),
  dashboard("onboarding.loading", () => "svg.spin", {
    reveal: true,
    overrides: [hold("GET", "/v1/admin/analytics/onboarding")],
  }),
  dashboard("onboarding.populated", text("Шаги тура — сколько пользователей дошло"), { reveal: true }),

  costs("populated", (t) => exactText(t("platform-admin:costs.chartTitle")), { scope: "full" }),
  costs("loading", () => "div.p-20 svg.spin", { overrides: [hold("GET", SUMMARY)] }),
  costs("by-model", () => 'text="anthropic/claude-opus-5.5"', {
    reveal: true,
    act: async (page, { t }) => button(page, t("platform-admin:costs.byModel")).click(),
  }),
  costs("by-role", () => 'td:text-is("transcription")', {
    reveal: true,
    act: async (page, { t }) => button(page, t("platform-admin:costs.byRole")).click(),
  }),
  costs("no-chart", (t) => exactText(t("platform-admin:costs.breakdown")), {
    overrides: [merged("GET", "/v1/admin/costs/timeline", { points: [] }, "у администратора есть расходы за месяц")],
  }),
  costs("breakdown-empty", (t) => exactText(t("platform-admin:costs.emptyBreakdown")), {
    reveal: true,
    overrides: [merged("GET", SUMMARY, { breakdown: [] }, "у администратора есть расходы")],
  }),
];
