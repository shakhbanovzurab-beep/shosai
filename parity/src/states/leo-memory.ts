// Окна памяти Leo в кабинете (шаг 5): сводка (ждёт, пуста, грузится, ответ на
// вопрос) и записи с подтверждением «забыть».

import type { Page } from "@playwright/test";

import { exactText, withText } from "../i18n/texts.ts";
import { cab } from "./leo-cabinet.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const SUMMARY = "/v1/memory/summary";

const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;
const button = (page: Page, name: string): ReturnType<Page["getByRole"]> =>
  page.getByRole("button", { name, exact: true });

async function openSummary(page: Page, { t }: StateContext): Promise<void> {
  await button(page, t("leo:leo.memoryManage")).click();
  await page.locator(dialog(t("leo:leo.memorySummaryTitle"))).waitFor();
}

async function openEntries(page: Page, context: StateContext): Promise<void> {
  await openSummary(page, context);
  await page.getByText(context.t("leo:leo.memoryEntriesLink", { count: 6 }), { exact: true }).click();
  await page.locator(dialog(context.t("leo:leo.memoryEntriesTitle"))).waitFor();
}

/** Сводка, собранная моделью ночью: заголовки `##`, без списков и выделений. */
const SUMMARY_TEXT = [
  "## Обзор",
  "Руководит продуктовым направлением в финтех-компании; ключевой клиент — Acme.",
  "",
  "## Работа",
  "Готовит запуск Acme к 1 сентября и сокращает офлайн-ивенты на 30 %.",
  "",
  "## Привычки",
  "Просит цифры таблицей, сроки датами и сводку договорённостей перед встречей.",
].join("\n");
const filledSummary = reply("GET", SUMMARY, 200, { text: SUMMARY_TEXT, items: 6, generated_at: "2026-07-17T09:00:00Z" },
  "сводку памяти пишет модель по ночам; на стенде её нет");

export const LEO_MEMORY_STATES: readonly State[] = [
  cab("memory-summary.pending", (t) => withText(dialog(t("leo:leo.memorySummaryTitle")), t("leo:leo.memorySummaryPending")), {
    act: openSummary,
  }),
  cab("memory-summary", () => 'text="Готовит запуск Acme к 1 сентября и сокращает офлайн-ивенты на 30 %."', {
    overrides: [filledSummary],
    act: openSummary,
  }),
  cab("memory-summary.empty", (t) => withText(dialog(t("leo:leo.memorySummaryTitle")), t("leo:leo.memoryEmpty")), {
    overrides: [reply("GET", SUMMARY, 200, { text: null, items: 0, generated_at: null }, "у засеянной персоны память не пуста")],
    act: openSummary,
  }),
  cab("memory-summary.loading", (t) => `${dialog(t("leo:leo.memorySummaryTitle"))} svg.spin`, {
    overrides: [hold("GET", SUMMARY)],
    act: async (page, { t }) => button(page, t("leo:leo.memoryManage")).click(),
  }),
  cab("memory-answer", () => 'text="Acme — ключевой клиент: запуск на платформе к 1 сентября."', {
    overrides: [filledSummary, reply("POST", `${SUMMARY}/ask`, 200, { text: "Acme — ключевой клиент: запуск на платформе к 1 сентября." },
      "ответ по памяти пишет модель; на стенде её нет")],
    act: async (page, context) => {
      await openSummary(page, context);
      const ask = page.locator(`[aria-label=${JSON.stringify(context.t("leo:leo.memoryAskPlaceholder"))}]`);
      await ask.fill("Что ты знаешь про Acme?");
      await ask.press("Enter");
    },
  }),
  cab("memory-entries", (t) => `${dialog(t("leo:leo.memoryEntriesTitle"))} >> ${exactText(t("leo:leo.forgotten"))}`, {
    scope: "full",
    act: openEntries,
  }),
  cab("memory-forget-confirm", (t) => dialog(t("leo:leo.forgetTitle")), {
    act: async (page, context) => {
      await openEntries(page, context);
      await page.locator(`[aria-label=${JSON.stringify(context.t("leo:leo.forget"))}]`).first().click();
    },
  }),
];
