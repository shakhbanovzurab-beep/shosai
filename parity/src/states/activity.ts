// «Активность» и «Поддержка» пользователя (шаг 7). Активность — у «Руководителя»
// (девять встреч за два месяца, ответов AI нет); обращения — у «Макса»: решённое,
// в работе с непрочитанным ответом и новое с картинкой.
//
// Вложения лежали бы в S3; без него черновик отдаёт их без ссылки — плашкой с
// именем и размером. Загрузка вложения без S3 отказывает — это и есть тост ошибки.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { button } from "../ui/admin-ui.ts";
import { merged } from "./admin-dashboard.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

function activity(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `analytics.${id}`, fixture: "analytics/home", scope: "single", marker, ...extra };
}

function support(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `support.${id}`, fixture: "support/list", scope: "single", marker, ...extra };
}

/**
 * Переключатель метрики: «Сессии», «Минуты» и прочие есть и у графика (первый),
 * и у календаря (второй) — группа выбирается по порядку.
 */
const metricTab = (index: number, label: (t: Translate) => string) => async (page: Page, { t }: StateContext): Promise<void> => {
  const groups = page.getByRole("group").filter({ has: page.getByRole("button", { name: t("analytics:analytics.mSessions"), exact: true }) });
  await groups.nth(index).getByRole("button", { name: label(t), exact: true }).click();
};

const usageTab = (label: (t: Translate) => string) => metricTab(0, label);

const openTicket = (subject: string) => async (page: Page): Promise<void> => {
  await page.getByRole("button", { name: subject }).first().click();
};

async function newTicket(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("support:support.newTicket")).click();
}

const ticketDialog = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("support:support.ticket"))}]`;

export const ACTIVITY_STATES: readonly State[] = [
  activity("home.populated", () => "table[role=grid]", { scope: "full" }),
  activity("home.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/me/analytics")] }),
  activity("usage.loading", (t) => exactText(t("analytics:analytics.usageChart")), {
    overrides: [hold("GET", "/v1/me/analytics/series")],
  }),
  activity("usage.metric-minutes", (t) => `button[aria-pressed=true]:text-is(${JSON.stringify(t("analytics:analytics.mMinutes"))})`, {
    act: usageTab((t) => t("analytics:analytics.mMinutes")),
  }),
  activity("usage.metric-avg", (t) => `button[aria-pressed=true]:text-is(${JSON.stringify(t("analytics:analytics.mAvg"))})`, {
    act: usageTab((t) => t("analytics:analytics.mAvg")),
  }),
  activity("usage.all-zero", (t) => exactText(t("common:chart.empty")), { act: usageTab((t) => t("analytics:analytics.mAi")) }),
  ...([["week", (t: Translate) => t("analytics:analytics.gWeek")], ["month", (t: Translate) => t("analytics:analytics.gMonth")],
    ["year", (t: Translate) => t("analytics:analytics.gYear")]] as const).map(([slug, label]) =>
    activity(`usage.gran-${slug}`, (t) => `button[aria-pressed=true]:text-is(${JSON.stringify(label(t))})`, {
      act: async (page, { t }) => button(page, label(t)).click(),
    })),
  activity("calendar.loading", () => "td[data-empty]", { reveal: true, overrides: [hold("GET", "/v1/me/analytics/activity")] }),
  activity("calendar.empty", (t) => exactText(t("analytics:analytics.calEmpty")), {
    reveal: true,
    overrides: [merged("GET", "/v1/me/analytics/activity", { days: [] }, "у «Руководителя» есть встречи")],
  }),
  activity("calendar.metric-minutes", () => "table[role=grid]", {
    reveal: true,
    act: metricTab(1, (t) => t("analytics:analytics.mMinutes")),
  }),
  activity("calendar.year", () => 'button[aria-pressed=true]:text-is("2026")', {
    reveal: true,
    act: async (page) => button(page, "2026").click(),
  }),
  activity("calendar.tooltip", () => "[role=tooltip].heat-tip", {
    keepPointer: true,
    act: async (page) => {
      // Подпись ячейки — дата на языке страницы; состояние снимается на ru.
      const cell = page.getByRole("gridcell", { name: /^14 июля 2026/ });
      await cell.scrollIntoViewIfNeeded();
      await cell.hover();
    },
  }),

  support("list.populated", () => 'button:has-text("Не подключается Google Календарь")', { scope: "full" }),
  support("list.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/me/tickets")] }),
  support("list.empty", (t) => exactText(t("support:support.empty")), {
    overrides: [reply("GET", "/v1/me/tickets", 200, [], "у «Макса» есть обращения")],
  }),
  support("faq.item-open", () => "#faq-panel-1", {
    reveal: true,
    act: async (page) => page.locator("button[aria-controls='faq-panel-1']").click(),
  }),
  support("new-ticket-modal", (t) => `dialog[aria-label=${JSON.stringify(t("support:support.newTicket"))}]`, { act: newTicket }),
  support("thread-modal", (t) => withText(ticketDialog(t), "kalendar.png"), { act: openTicket("Не подключается Google Календарь") }),
  support("thread-modal.resolved", (t) => withText(ticketDialog(t), "DOCX"), { act: openTicket("Как скачать стенограмму встречи в Word?") }),
  support("thread-modal.loading", (t) => `${ticketDialog(t)} svg.spin`, {
    overrides: [hold("GET", "/v1/me/tickets/{id}")],
    act: openTicket("Не подключается Google Календарь"),
  }),
  support("delete-confirm", (t) => withText(`dialog[aria-label=${JSON.stringify(t("support:support.delete"))}]`,
    t("support:support.deleteConfirm")), {
    act: async (page, { t }) => page.locator(`button[aria-label=${JSON.stringify(t("support:support.delete"))}]`).first().click(),
  }),
  support("attach-error", (t) => withText("[role=alert]", t("support:support.attachFailed")), {
    expectsAlert: true,
    overrides: [reply("POST", "/v1/me/tickets/attachments", 503, { detail: "storage_unavailable" },
      "вложения хранятся в S3; ответ — как у черновика без него")],
    act: async (page, context) => {
      await newTicket(page, context);
      await page.locator(`input[type=file][aria-label=${JSON.stringify(context.t("support:support.attach"))}]`)
        .setInputFiles({ name: "skrinshot.png", mimeType: "image/png", buffer: Buffer.from("parity") });
    },
  }),
];
