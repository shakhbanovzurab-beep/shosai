// Поддержка и рассылки, сборки клиентов, ошибки клиентов, платформенные промпты
// и партнёры в админке (шаг 7). Тексты вшиты по-русски — только ru.
//
// Треды открываются только уже прочитанные (#100001 и #100002): открытие пишет
// метку «прочитано». Отправка ответа, смена статуса, удаление и загрузка сборки
// меняют данные — их ответы синтетика.

import type { Page } from "@playwright/test";

import type { Translate } from "../i18n/texts.ts";
import { button, choose } from "../ui/admin-ui.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State } from "./types.ts";

const RU: readonly string[] = ["ru"];
const TICKET = "/v1/admin/tickets/{id}";
const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;
const ALERT = (value: string) => (): string => `[role=alert]:has-text(${JSON.stringify(value)})`;

function admin(page: string, id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.${page}.${id}`, fixture: `admin/${page}`, scope: "single", languages: RU, marker, ...extra };
}

const openTicket = (subject: string) => async (page: Page): Promise<void> => {
  await page.getByRole("button", { name: subject }).first().click();
};

async function broadcasts(page: Page): Promise<void> {
  await button(page, "Рассылки").click();
}

async function sendToBanned(page: Page): Promise<void> {
  await broadcasts(page);
  await choose(page, "Все пользователи", "Один пользователь");
  await page.getByLabel("Email получателя", { exact: true }).fill("banned@parity.test");
  await page.getByLabel("Тема", { exact: true }).fill("Ответ на ваше обращение");
  await page.getByLabel("Сообщение", { exact: true }).fill("Мы разблокировали ваш аккаунт.");
  await button(page, "Отправить рассылку").click();
}

async function uploadBuild(page: Page): Promise<void> {
  await page.getByPlaceholder("1.4.3", { exact: true }).fill("1.4.6");
  await page.locator("input[type=file]").setInputFiles({ name: "Whisperer-1.4.6.dmg", mimeType: "application/octet-stream",
    buffer: Buffer.from("parity build") });
  await button(page, "Загрузить и опубликовать").click();
}

export const ADMIN_OPS_STATES: readonly State[] = [
  admin("support", "tickets.populated", text("Добавьте горячую клавишу для паузы записи"), { scope: "full" }),
  admin("support", "tickets.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/tickets")] }),
  admin("support", "tickets.empty", () => '[data-slot=empty-title]:has-text("Тикетов нет")', {
    overrides: [reply("GET", "/v1/admin/tickets", 200, [], "в засеве есть обращения")],
  }),
  admin("support", "tickets.filter", () => '[role=combobox]:has-text("Открытые")', {
    act: async (page) => choose(page, "Все статусы", "Открытые"),
  }),
  admin("support", "tickets.status-menu", () => '[role=option]:has-text("В работе")', {
    act: async (page) => page.locator("[role=combobox]").filter({ hasText: "Открыт" }).first().click(),
  }),
  admin("support", "tickets.delete-confirm", () => 'dialog[aria-label="Удалить тикет"]', {
    act: async (page) => page.getByTitle("Удалить тикет", { exact: true }).first().click(),
  }),
  admin("support", "ticket-modal", () => "dialog >> text=Запись останавливается примерно через 40 минут",
    { act: openTicket("Запись обрывается на длинных встречах") }),
  admin("support", "ticket-modal.loading", () => "dialog svg.spin", {
    overrides: [hold("GET", TICKET)],
    act: openTicket("Запись обрывается на длинных встречах"),
  }),
  admin("support", "ticket-modal.resolved", () => "dialog >> text=Получилось, спасибо!", {
    act: openTicket("Как скачать стенограмму встречи в Word?"),
  }),
  admin("support", "broadcast.form", text("История рассылок"), { act: broadcasts }),
  admin("support", "broadcast.single-user", () => 'input[placeholder="user@example.com"]', {
    act: async (page) => {
      await broadcasts(page);
      await choose(page, "Все пользователи", "Один пользователь");
    },
  }),
  admin("support", "broadcast.telegram", () => "text=Канал Telegram пока не подключён", {
    act: async (page) => {
      await broadcasts(page);
      await choose(page, "Email", "Telegram");
    },
  }),
  admin("support", "broadcast.delete-confirm", () => 'dialog[aria-label="Удалить рассылку"]', {
    act: async (page) => {
      await broadcasts(page);
      await page.getByTitle("Удалить", { exact: true }).first().click();
    },
  }),
  admin("support", "broadcast.error", text("Получатель не найден или неактивен"), { act: sendToBanned }),

  admin("app", "populated", text("снята"), { scope: "full" }),
  admin("app", "loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/app/builds")] }),
  admin("app", "empty", text("Сборок ещё нет — загрузите первую ниже."), {
    overrides: [reply("GET", "/v1/admin/app/builds", 200, [], "сборки засева видны всем пользователям")],
  }),
  admin("app", "notify", ALERT("Получателей нет"), {
    expectsAlert: true,
    act: async (page) => button(page, "Оповестить о новой версии").click(),
  }),
  admin("app", "notify-error", ALERT("Не удалось поставить рассылку"), {
    expectsAlert: true,
    overrides: [serverError("POST", "/v1/admin/app/builds/notify")],
    act: async (page) => button(page, "Оповестить о новой версии").click(),
  }),
  admin("app", "upload-error", text("Сборка тяжелее 500 МБ — сервер её не принял."), {
    overrides: [reply("POST", "/v1/admin/app/builds", 413, { detail: "file_too_large" },
      "файл больше 500 МБ стенд записи не отправлял")],
    act: uploadBuild,
  }),

  admin("client-errors", "populated", text("NSInvalidArgumentException"), { scope: "full" }),
  admin("client-errors", "loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/client-errors")] }),
  admin("client-errors", "empty", () => '[data-slot=empty-title]:has-text("Ошибок не найдено")', {
    overrides: [reply("GET", "/v1/admin/client-errors", 200, { items: [], total: 0, limit: 50, offset: 0 },
      "в засеве есть ошибки клиентов")],
  }),
  admin("client-errors", "paginated", text("51–52 из 52"), { act: async (page) => button(page, "Вперёд →").click() }),
  admin("client-errors", "filter-platform", () => '[role=combobox]:has-text("macOS")', {
    act: async (page) => choose(page, "Все платформы", "macOS"),
  }),
  admin("client-errors", "filter-days", () => '[role=combobox]:has-text("Сутки")', {
    act: async (page) => choose(page, "За всё время", "Сутки"),
  }),
  admin("client-errors", "drawer.loading", () => "div[role=presentation] svg.spin", {
    overrides: [hold("GET", "/v1/admin/client-errors/{id}")],
    act: async (page) => page.getByRole("button", { name: "Открыть", exact: true }).first().click(),
  }),
  admin("client-errors", "drawer.populated", text("Окружение"), {
    act: async (page) => page.getByRole("button", { name: "Открыть", exact: true }).first().click(),
  }),

  admin("prompts", "populated", () => '[aria-label="Guardrail — жёсткие правила"]', { scope: "full" }),
  admin("prompts", "loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/prompts")] }),
  admin("prompts", "empty", () => '[aria-label="Guardrail — жёсткие правила"]:placeholder-shown', {
    overrides: [reply("GET", "/v1/admin/prompts", 200, [], "в засеве два слоя из трёх заполнены")],
  }),
  admin("prompts", "save-error", text("Не сохранилось — проверьте связь и повторите"), {
    overrides: [serverError("PATCH", "/v1/admin/prompts/{id}")],
    act: async (page) => button(page, "Сохранить").first().click(),
  }),

  admin("affiliates", "populated", text("Канал не по теме продукта"), { scope: "full" }),
  admin("affiliates", "loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/affiliates")] }),
  admin("affiliates", "partners.empty", text("Заявок пока нет."), {
    overrides: [reply("GET", "/v1/admin/affiliates", 200, [], "в засеве есть партнёры")],
  }),
  admin("affiliates", "payouts.empty", () => "text=Заявок на выплату нет", {
    overrides: [reply("GET", "/v1/admin/affiliates/payouts", 200, [], "в засеве есть выплаты")],
  }),
];
