// Пользователи и тарифы в админке (шаг 7): список с поиском, фильтром и
// страницами, ящик пользователя (обычный, замороженный, забаненный, выбор
// тарифа); карточки тарифов, промокоды, форма промокода и окно тарифа с отказами.
// Тексты вшиты по-русски — только ru.

import type { Page } from "@playwright/test";

import type { Translate } from "../i18n/texts.ts";
import { button, choose } from "../ui/admin-ui.ts";
import { merged } from "./admin-dashboard.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State } from "./types.ts";

const RU: readonly string[] = ["ru"];
const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;

function users(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.users.${id}`, fixture: "admin/users", scope: "single", languages: RU, marker, ...extra };
}

function tariffs(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.tariffs.${id}`, fixture: "admin/tariffs", scope: "single", languages: RU, marker, ...extra };
}

const openUser = (email: string) => async (page: Page): Promise<void> => {
  await page.locator(`tr:has-text(${JSON.stringify(email)})`).getByRole("button", { name: "Открыть" }).click();
};

const search = (query: string) => async (page: Page): Promise<void> => {
  await page.getByPlaceholder("Поиск по email/имени", { exact: true }).fill(query);
};

async function promo(page: Page): Promise<void> {
  await page.getByPlaceholder("SUMMER25", { exact: true }).fill("SUMMER25");
  await page.getByLabel("Скидка, % (1–100)", { exact: true }).fill("25");
  await button(page, "Создать").click();
}

const drawer = "div[role=presentation]";

export const ADMIN_USERS_STATES: readonly State[] = [
  users("populated", text("sharer2@parity.test"), { scope: "full" }),
  users("loading", () => "div.p-10 svg.spin", { overrides: [hold("GET", "/v1/admin/users")] }),
  users("empty", () => '[data-slot=empty-title]:has-text("Никого не нашлось")', { act: search("nobody-here") }),
  users("search", text("sharer2@parity.test"), { act: search("sharer") }),
  users("filter-frozen", () => '[role=combobox]:has-text("Замороженные")', {
    act: async (page) => choose(page, "Все статусы", "Замороженные"),
  }),
  users("filter-banned", () => '[role=combobox]:has-text("Забаненные")', {
    act: async (page) => {
      await choose(page, "Все статусы", "Замороженные");
      await choose(page, "Замороженные", "Забаненные");
    },
  }),
  users("paginated", () => 'button:has-text("Вперёд →"):enabled', {
    overrides: [merged("GET", "/v1/admin/users", { total: 73 }, "в засеве 22 пользователя — меньше страницы")],
  }),
  users("user-drawer", text("Верификация (KYC)"), { act: openUser("pro@parity.test") }),
  users("user-drawer.loading", () => `${drawer} svg.spin`, {
    overrides: [hold("GET", "/v1/admin/users/{id}")],
    act: openUser("pro@parity.test"),
  }),
  users("user-drawer.frozen", () => `${drawer} button:has-text("Разморозить")`, { act: openUser("frozen@parity.test") }),
  users("user-drawer.banned", () => `${drawer} button:has-text("Забанить"):disabled`, { act: openUser("banned@parity.test") }),
  users("user-drawer.tariff-select", () => '[role=option]:has-text("Max")', {
    act: async (page) => {
      await openUser("pro@parity.test")(page);
      await page.locator(`${drawer} [role=combobox]`).filter({ hasText: "Pro (31 день)" }).click();
    },
  }),

  tariffs("populated", text("Не продаётся за $ и € — цена не задана"), { scope: "full" }),
  tariffs("loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/tariffs")] }),
  tariffs("promos.loading", text("Промокоды"), { overrides: [hold("GET", "/v1/admin/promocodes")] }),
  tariffs("promos.empty", text("Промокодов пока нет — создайте первый в форме ниже."), {
    overrides: [reply("GET", "/v1/admin/promocodes", 200, [], "в засеве есть промокоды")],
  }),
  tariffs("promo-form.bonus-days", () => 'label:has-text("Дней (1–365)")', {
    act: async (page) => choose(page, "Скидка, %", "Бонусные дни"),
  }),
  tariffs("promo-form.error-409", text("Такой код уже существует"), { reveal: true, act: promo }),
  tariffs("promo-form.error", text("Ошибка создания промокода"), {
    reveal: true,
    overrides: [serverError("POST", "/v1/admin/promocodes")],
    act: promo,
  }),
  tariffs("modal-new", () => 'label:has-text("Лимит минут (пусто = безлимит)")', {
    act: async (page) => button(page, "Новый тариф").click(),
  }),
  tariffs("modal-edit", text("Изменить тариф"), { act: async (page) => button(page, "Изменить").first().click() }),
  tariffs("modal-save-error", text("Tariff code already exists: free"), {
    act: async (page) => {
      await button(page, "Новый тариф").click();
      const modal = page.locator(drawer);
      await modal.getByLabel("Код", { exact: true }).fill("free");
      await modal.getByLabel("Название", { exact: true }).fill("Free");
      await modal.getByRole("button", { name: "Сохранить", exact: true }).click();
    },
  }),
];
