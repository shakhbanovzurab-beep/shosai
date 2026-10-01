// Визиты админки: дашборд, продуктовая аналитика, пользователи, тарифы, деньги и
// финансы. Безопасность, поддержка, сборки, ошибки, промпты, партнёры и
// удовлетворённость — admin-ops.ts. Состояния — parity/inventory/admin-analytics-support.md.
//
// Админ-экраны черновик пишет по-русски без каталога переводов: их визиты пишутся
// только на ru, маркеры — строки. «Деньги» переведены и пишутся на обоих языках.
//
// Визиты не меняют данных: обход открывает разделы, ящики, фильтры и страницы, а
// из действий выполняет только отказы (промокод и тариф с занятым кодом — 409).
// Каждое состояние повторяет начало такого обхода и находит свои ответы в фикстуре.

import type { Page } from "@playwright/test";

import { exactText } from "../../i18n/texts.ts";
import { analyticsSection, button, choose, step } from "../../ui/admin-ui.ts";
import type { Visit } from "./types.ts";

const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;
const RU: readonly string[] = ["ru"];

/** Измерения разбивки дашборда по порядку обхода: каждое — свой запрос. */
export const DRILL_DIMENSIONS = ["Пользователи", "Тарифы", "Провайдеры", "Роли", "Объекты (сессии)"] as const;

async function walkDashboard(page: Page): Promise<void> {
  let current = "Модели";
  for (const dimension of DRILL_DIMENSIONS) {
    await step(page, () => choose(page, current, dimension));
    current = dimension;
  }
  await step(page, () => choose(page, current, "Модели"));
  const sort = page.locator('button[aria-label="Сортировать по значению"]');
  await step(page, () => sort.click());
  await step(page, () => sort.click());
  await step(page, () => button(page, "Вперёд →").click());
  await step(page, () => button(page, "← Назад").click());
  await step(page, async () => {
    await page.getByLabel("Начало периода", { exact: true }).fill("2026-07-01");
    await page.getByLabel("Конец периода", { exact: true }).fill("2026-07-15");
  });
}

/** Разделы продуктовой аналитики по порядку списка «Раздел». */
async function walkAnalytics(page: Page): Promise<void> {
  const open = async (section: string): Promise<void> => {
    await step(page, () => analyticsSection(page, section));
    await step(page, () => choose(page, section, "Сводка"));
  };
  await open("Цели");
  await open("Находки");
  await step(page, () => analyticsSection(page, "Сторожа"));
  await step(page, () => button(page, "Проверить вхолостую").click());
  await step(page, () => choose(page, "Сторожа", "Сводка"));
  await step(page, () => analyticsSection(page, "Воронки"));
  await step(page, () => choose(page, "От лендинга до регистрации", "Встреча превратилась в пользу"));
  await step(page, () => choose(page, "Воронки", "Сводка"));
  await open("Когорты");
  await open("Модули");
  await step(page, () => analyticsSection(page, "Конструктор"));
  await step(page, () => choose(page, "выберите метрику", "Начатые встречи"));
  await step(page, () => choose(page, "Конструктор", "Сводка"));
  await step(page, () => analyticsSection(page, "Словарь метрик"));
  await step(page, () => page.getByRole("button", { name: /^Регистрации/ }).first().click());
  await step(page, () => choose(page, "Словарь метрик", "Сводка"));
  await open("Связи");
}

/** Поиск, фильтры статуса и ящики пользователя: обычного, замороженного, забаненного. */
async function walkUsers(page: Page): Promise<void> {
  const open = async (email: string): Promise<void> => {
    await step(page, () => page.locator(`tr:has-text(${JSON.stringify(email)})`).getByRole("button", { name: "Открыть" }).click());
    await step(page, () => button(page, "Закрыть").click());
  };
  await open("pro@parity.test");
  await open("frozen@parity.test");
  await open("banned@parity.test");
  await step(page, () => page.getByPlaceholder("Поиск по email/имени", { exact: true }).fill("sharer"));
  await step(page, () => page.getByPlaceholder("Поиск по email/имени", { exact: true }).fill("nobody-here"));
  await step(page, () => page.getByPlaceholder("Поиск по email/имени", { exact: true }).fill(""));
  for (const [from, to] of [["Все статусы", "Замороженные"], ["Замороженные", "Забаненные"], ["Забаненные", "Активные"]] as const) {
    await step(page, () => choose(page, from, to));
  }
}

/** Отказы без изменений: промокод с занятым кодом и тариф с кодом free — 409. */
async function walkTariffs(page: Page): Promise<void> {
  await page.getByPlaceholder("SUMMER25", { exact: true }).fill("SUMMER25");
  await page.getByLabel("Скидка, % (1–100)", { exact: true }).fill("25");
  await step(page, () => button(page, "Создать").click());
  await step(page, () => button(page, "Новый тариф").click());
  const modal = page.locator("div[role=presentation]");
  await modal.getByLabel("Код", { exact: true }).fill("free");
  await modal.getByLabel("Название", { exact: true }).fill("Free");
  await step(page, () => modal.getByRole("button", { name: "Сохранить", exact: true }).click());
}

/** Фильтры статуса, отказ в автоматическом возврате и сводка по пользователю (закрывается щелчком мимо). */
async function walkFinance(page: Page): Promise<void> {
  let current = "Все статусы";
  for (const status of ["Успешные", "Ожидание", "Ошибки", "Возвраты", "Все статусы"]) {
    await step(page, () => choose(page, current, status));
    current = status;
  }
  await step(page, () => page.locator('tr:has-text("max@parity.test")').getByRole("button", { name: "Возврат" }).click());
  await step(page, () => page.locator('dialog[aria-label="Деньги вернули в кабинете эквайера?"]').getByRole("button", { name: "Отмена", exact: true }).last().click());
  await step(page, () => page.locator('button[aria-label="Сводка по pro@parity.test"]').first().click());
}

export const ADMIN_VISITS: readonly Visit[] = [
  { id: "admin/dashboard", persona: "admin", url: "/app/dashboard", languages: RU, marker: text("Онбординг новых пользователей"),
    act: walkDashboard },
  { id: "admin/analytics", persona: "admin", url: "/app/admin/analytics", languages: RU,
    marker: () => "text=четыре вопроса за полминуты", act: walkAnalytics },
  { id: "admin/users", persona: "admin", url: "/app/admin/users", languages: RU, marker: text("Регистрация"), act: walkUsers },
  { id: "admin/tariffs", persona: "admin", url: "/app/admin/tariffs", languages: RU, marker: text("Такой код уже существует"),
    act: walkTariffs },
  {
    id: "admin/costs",
    persona: "admin",
    url: "/app/costs",
    marker: (t) => exactText(t("platform-admin:costs.breakdown")),
    act: async (page, { t }) => {
      await step(page, () => button(page, t("platform-admin:costs.byModel")).click());
      await step(page, () => button(page, t("platform-admin:costs.byRole")).click());
    },
  },
  { id: "admin/finance", persona: "admin", url: "/app/admin/finance", languages: RU, marker: text("Расходы по моделям"),
    act: walkFinance },
];
