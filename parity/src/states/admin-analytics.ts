// Продуктовая аналитика (шаг 7): сводка недели, цели, находки, сторожа с проверкой
// вхолостую, воронки, когорты, модули, конструктор графика, словарь метрик и
// связи. Каждый раздел — загрузка, данные и пустой вариант. Раздел выбирается
// списком «Раздел»: адреса у разделов нет. Тексты вшиты по-русски — только ru.
//
// Данные — события засева (recording/seed/analytics_seed.py): пустые варианты
// там же получить нельзя, они — синтетика.

import type { Page } from "@playwright/test";

import type { Translate } from "../i18n/texts.ts";
import { analyticsSection, button, choose } from "../ui/admin-ui.ts";
import { merged } from "./admin-dashboard.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const RU: readonly string[] = ["ru"];
const SEEDED = "события засева дают данные этого раздела";

const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;
const contains = (value: string) => (): string => `text=${value}`;

function analytics(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.analytics.${id}`, fixture: "admin/analytics", scope: "single", languages: RU, marker, ...extra };
}

/** Состояние раздела: открыть его в списке «Раздел», затем, если нужно, действие внутри. */
function section(name: string, id: string, marker: (t: Translate) => string, extra: Partial<State> = {},
                 then?: (page: Page, context: StateContext) => Promise<void>): State {
  return analytics(id, marker, {
    ...extra,
    act: async (page, context) => {
      await analyticsSection(page, name);
      if (then !== undefined) await then(page, context);
    },
  });
}

export const ADMIN_ANALYTICS_STATES: readonly State[] = [
  analytics("overview.populated", text("Растём ли мы?"), { scope: "full" }),
  analytics("overview.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/overview")] }),
  analytics("overview.empty-week", contains("нет ни одного наблюдения"), {
    overrides: [merged("GET", "/v1/admin/overview", { is_empty: true }, SEEDED)],
  }),
  analytics("overview.nothing-burning", text("Ничего не горит: цели идут по плану, отклонений не обнаружено."), {
    overrides: [merged("GET", "/v1/admin/overview", { targets: [], findings: [], weak: [] }, SEEDED)],
  }),
  analytics("overview.questions-empty", text("Метрики роста ещё не считаются по неделям."), {
    overrides: [merged("GET", "/v1/admin/overview", { metrics: [] }, SEEDED)],
  }),

  section("Цели", "targets.populated", text("Цели · худшее сверху")),
  section("Цели", "targets.loading", () => "svg.spin", { overrides: [hold("POST", "/v1/admin/targets/progress")] }),
  section("Цели", "targets.empty", text("Цели не объявлены."), {
    overrides: [merged("POST", "/v1/admin/targets/progress", { targets: [] }, SEEDED)],
  }),
  section("Находки", "findings.populated", contains("крупнейшее отклонение первым")),
  section("Находки", "findings.loading", () => "svg.spin", { overrides: [hold("POST", "/v1/admin/insights/anomalies")] }),
  section("Находки", "findings.empty", text("Отклонений не обнаружено: все проверенные метрики держатся своей нормы."), {
    overrides: [merged("POST", "/v1/admin/insights/anomalies", { findings: [] }, SEEDED)],
  }),
  section("Сторожа", "alerts.rules", contains("Правил объявлено:")),
  section("Сторожа", "alerts.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/alerts")] }),
  section("Сторожа", "alerts.dry-run-pending", text("Проверяю…"), { overrides: [hold("POST", "/v1/admin/alerts/check")] },
    async (page) => button(page, "Проверить вхолостую").click()),
  section("Сторожа", "alerts.dry-run-result", text("сработало бы"), {},
    async (page) => button(page, "Проверить вхолостую").click()),
  section("Воронки", "funnels.populated", contains("от начала:")),
  section("Воронки", "funnels.loading", () => "svg.spin", { overrides: [hold("POST", "/v1/admin/funnels/{slug}/run")] }),
  section("Воронки", "funnels.empty", contains("За период нет ни одного входа в воронку."), {
    overrides: [reply("POST", "/v1/admin/funnels/{slug}/run", 200, [], SEEDED)],
  }),
  section("Воронки", "funnels.switch", contains("Встреча превратилась в пользу ·"), {},
    async (page) => choose(page, "От лендинга до регистрации", "Встреча превратилась в пользу")),
  section("Когорты", "cohorts.populated", contains("Удержание по месяцу установки клиента · по месяцам")),
  section("Когорты", "cohorts.loading", () => "svg.spin", { overrides: [hold("POST", "/v1/admin/cohorts/{slug}/matrix")] }),
  section("Когорты", "cohorts.empty", text("За период не набралось ни одной когорты."), {
    overrides: [merged("POST", "/v1/admin/cohorts/{slug}/matrix", { rows: [] }, SEEDED)],
  }),
  section("Модули", "health.populated", contains("Активных за период:")),
  section("Модули", "health.loading", () => "svg.spin", { overrides: [hold("POST", "/v1/admin/feature-health")] }),
  section("Модули", "health.empty", text("Модули не объявлены."), {
    overrides: [merged("POST", "/v1/admin/feature-health", { modules: [] }, SEEDED)],
  }),
  section("Конструктор", "explorer.initial", contains("Выберите метрику: спрашивать можно только объявленное")),
  section("Конструктор", "explorer.loading", () => "svg.spin", { overrides: [hold("POST", "/v1/admin/metrics/query")] },
    async (page) => choose(page, "выберите метрику", "Начатые встречи")),
  section("Конструктор", "explorer.chart", () => "svg[role=img]", {},
    async (page) => choose(page, "выберите метрику", "Начатые встречи")),
  section("Словарь метрик", "dictionary.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/metrics")] }),
  section("Словарь метрик", "dictionary.populated", () => "button[aria-expanded]"),
  section("Словарь метрик", "dictionary.passport-open", text("Версия определения"), {},
    async (page) => page.getByRole("button", { name: /^Регистрации/ }).first().click()),
  section("Словарь метрик", "dictionary.empty", text("Метрики не объявлены."), {
    overrides: [reply("GET", "/v1/admin/metrics", 200, [], SEEDED)],
  }),
  section("Связи", "graph.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/metrics/graph")] }),
  section("Связи", "graph.populated", text("Уровень 0 · меняется само")),
  section("Связи", "graph.empty", text("Метрики не объявлены."), {
    overrides: [merged("GET", "/v1/admin/metrics/graph", { nodes: [], edges: [], dangling: [] }, SEEDED)],
  }),
];
