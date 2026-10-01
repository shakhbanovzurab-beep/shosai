// Визиты админки: безопасность, поддержка и рассылки, сборки клиентов, ошибки
// клиентов, платформенные промпты, партнёры, удовлетворённость. И домашняя
// «Активность» и «Поддержка» пользователя. Правила — в начале admin.ts.
//
// Открытие обращения отмечает его прочитанным: обходы открывают только уже
// прочитанные (решённое и то, где последний ответ — поддержки). Рассылка одному
// получателю уходит на заблокированного — черновик отвечает 404 и ничего не пишет.
// Оповещение о версии ставит письмо в очередь, которую на стенде никто не читает.

import type { Page } from "@playwright/test";

import { exactText, withText } from "../../i18n/texts.ts";
import { button, choose, step } from "../../ui/admin-ui.ts";
import type { Visit, VisitContext } from "./types.ts";

const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;
const RU: readonly string[] = ["ru"];

/** Цепочка фильтров: каждый переход — из текущего значения в следующее. */
async function filters(page: Page, chain: readonly string[]): Promise<void> {
  for (let index = 1; index < chain.length; index += 1) {
    const [from = "", to = ""] = [chain[index - 1], chain[index]];
    await step(page, () => choose(page, from, to));
  }
}

/** Обращение открывается кнопкой с темой, номером и числом сообщений. */
async function openThread(page: Page, subject: string): Promise<void> {
  await step(page, () => page.getByRole("button", { name: subject }).first().click());
  await step(page, () => page.keyboard.press("Escape"));
}

async function walkSecurity(page: Page): Promise<void> {
  await step(page, () => button(page, "Очередь abuse").click());
  await step(page, () => page.locator('[aria-label="Открыть аудит abuser@parity.test"]').click());
  await step(page, () => button(page, "Очередь abuse").click());
  await step(page, () => page.locator('[aria-label="Открыть аудит trusted@parity.test"]').click());
}

async function walkSupport(page: Page): Promise<void> {
  await openThread(page, "Как скачать стенограмму встречи в Word?");
  await openThread(page, "Запись обрывается на длинных встречах");
  await filters(page, ["Все статусы", "Открытые", "В работе", "Решённые", "Все статусы"]);
  await step(page, () => button(page, "Рассылки").click());
  await step(page, () => choose(page, "Все пользователи", "Один пользователь"));
  await page.getByLabel("Email получателя", { exact: true }).fill("banned@parity.test");
  await page.getByLabel("Тема", { exact: true }).fill("Ответ на ваше обращение");
  await page.getByLabel("Сообщение", { exact: true }).fill("Мы разблокировали ваш аккаунт.");
  await step(page, () => button(page, "Отправить рассылку").click());
}

async function walkClientErrors(page: Page): Promise<void> {
  const search = page.getByPlaceholder("Поиск по email", { exact: true });
  await step(page, () => search.fill("pro@"));
  await step(page, () => search.fill(""));
  await filters(page, ["Все платформы", "macOS", "Все платформы"]);
  await filters(page, ["Все уровни", "Fatal", "Все уровни"]);
  await filters(page, ["Все категории", "Краши", "Все категории"]);
  await filters(page, ["За всё время", "Сутки", "7 дней", "За всё время"]);
  await step(page, () => button(page, "Вперёд →").click());
  await step(page, () => button(page, "← Назад").click());
  await step(page, () => page.getByRole("button", { name: "Открыть", exact: true }).first().click());
}

async function walkSatisfaction(page: Page): Promise<void> {
  await filters(page, ["90 дней", "30 дней", "90 дней"]);
  await filters(page, ["Все ответы", "Только пользователи", "Все ответы"]);
  await filters(page, ["Любой пол", "Женщины", "Любой пол"]);
}

/** Шаг графика и год календаря: каждый — свой запрос. */
async function walkActivity(page: Page, { t }: VisitContext): Promise<void> {
  for (const granularity of [t("analytics:analytics.gWeek"), t("analytics:analytics.gMonth"), t("analytics:analytics.gYear")]) {
    await step(page, () => button(page, granularity).click());
  }
  await step(page, () => button(page, "2026").click());
}

export const ADMIN_OPS_VISITS: readonly Visit[] = [
  { id: "admin/security", persona: "admin", url: "/app/admin/security", languages: RU, marker: text("score 0.61"),
    act: walkSecurity },
  { id: "admin/support", persona: "admin", url: "/app/admin/support", languages: RU,
    marker: text("Получатель не найден или неактивен"), act: walkSupport },
  {
    id: "admin/app",
    persona: "admin",
    url: "/app/admin/app",
    languages: RU,
    marker: () => withText("[role=alert], [role=status]", "Получателей нет"),
    act: async (page) => step(page, () => button(page, "Оповестить о новой версии").click()),
  },
  { id: "admin/client-errors", persona: "admin", url: "/app/admin/client-errors", languages: RU, marker: text("Окружение"),
    act: walkClientErrors },
  { id: "admin/prompts", persona: "admin", url: "/app/admin/prompts", languages: RU,
    marker: () => '[aria-label="Guardrail — жёсткие правила"]' },
  { id: "admin/affiliates", persona: "admin", url: "/app/admin/affiliates", languages: RU, marker: text("Канал не по теме продукта") },
  { id: "admin/satisfaction", persona: "admin", url: "/app/admin/satisfaction", languages: RU, marker: text("Средняя оценка"),
    act: walkSatisfaction },

  { id: "analytics/home", persona: "lead", url: "/app/analytics", marker: (t) => exactText(t("analytics:analytics.calendar")),
    act: walkActivity },
  {
    id: "support/list",
    persona: "max",
    url: "/app/support",
    marker: (t) => exactText(t("support:faq.title")),
    act: async (page) => {
      await openThread(page, "Не подключается Google Календарь");
      await openThread(page, "Как скачать стенограмму встречи в Word?");
    },
  },
];
