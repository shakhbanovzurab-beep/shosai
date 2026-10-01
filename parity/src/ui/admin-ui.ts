// Действия на экранах админки, общие для визитов записи и состояний съёмки.
// Админ-экраны черновик пишет по-русски без каталога переводов, поэтому здесь
// строки, а не ключи.

import type { Locator, Page } from "@playwright/test";

/** Кнопка по точному имени. */
export const button = (page: Page, name: string): Locator => page.getByRole("button", { name, exact: true });

/**
 * Выбор в списке: у списка Radix доступного имени нет — текущее значение лежит
 * в нём текстом; у списка с поиском (12 вариантов и больше) — кнопка с ним.
 */
export async function choose(page: Page, current: string, option: string): Promise<void> {
  const radix = page.locator("[role=combobox]").filter({ has: page.getByText(current, { exact: true }) });
  await radix.or(button(page, current)).first().click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

/** Раздел продуктовой аналитики: список «Раздел», сейчас — «Сводка». */
export async function analyticsSection(page: Page, section: string): Promise<void> {
  await choose(page, "Сводка", section);
}

/** Незавершённые запросы к API на странице и время последнего события сети. */
interface Traffic {
  readonly pending: Set<object>;
  last: number;
}

const traffic = new WeakMap<Page, Traffic>();

function watch(page: Page): Traffic {
  const known = traffic.get(page);
  if (known !== undefined) return known;
  const state: Traffic = { pending: new Set(), last: Date.now() };
  const isApi = (url: string): boolean => new URL(url).pathname.startsWith("/v1/");
  page.on("request", (request) => {
    if (!isApi(request.url())) return;
    state.pending.add(request);
    state.last = Date.now();
  });
  const done = (request: object): void => {
    state.pending.delete(request);
    state.last = Date.now();
  };
  page.on("requestfinished", done);
  page.on("requestfailed", done);
  traffic.set(page, state);
  return state;
}

/**
 * Действие и тишина API после него: 400 мс без запросов к /v1. Ответ из кэша
 * react-query запроса не шлёт, поэтому ждать конкретный ответ нельзя.
 */
export async function step(page: Page, action: () => Promise<void>): Promise<void> {
  const state = watch(page);
  await action();
  const started = Date.now();
  await page.waitForTimeout(150);
  while (state.pending.size > 0 || Date.now() - Math.max(state.last, started) < 400) {
    if (Date.now() - started > 15_000) throw new Error("API не затих за 15 с после действия");
    await page.waitForTimeout(50);
  }
}
