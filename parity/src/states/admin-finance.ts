// Финансы и безопасность в админке (шаг 7): эквайринг, транзакции с фильтром,
// отказ в автоматическом возврате, сводка по пользователю; шеринг аккаунтов и
// журнал ошибок, очередь abuse и аудит решений. Тексты вшиты по-русски — только ru.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import type { Translate } from "../i18n/texts.ts";
import { button, choose } from "../ui/admin-ui.ts";
import { merged } from "./admin-dashboard.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State } from "./types.ts";

const RU: readonly string[] = ["ru"];
const TRANSACTIONS = "/v1/admin/finance/transactions";
const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;

function finance(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.finance.${id}`, fixture: "admin/finance", scope: "single", languages: RU, marker, ...extra };
}

function security(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.security.${id}`, fixture: "admin/security", scope: "single", languages: RU, marker, ...extra };
}

const method = (name: string, enabled: boolean, position: number, recurring: boolean): JsonValue =>
  ({ method: name, enabled, position, configured: true, supports_recurring: recurring });

/** Маршруты оплаты, в которых для валютных платежей все способы выключены. */
const FX_CLOSED: JsonValue = {
  scopes: [
    { scope: "RUB", active_method: "tbank",
      methods: [method("tbank", true, 0, true), method("lava", true, 1, false), method("cloudpayments", false, 2, true)] },
    { scope: "FX", active_method: null,
      methods: [method("lava", false, 0, false), method("lava_paypal", false, 1, false), method("cloudpayments", false, 2, true)] },
  ],
};

const refund = async (page: Page): Promise<void> => {
  await page.locator('tr:has-text("max@parity.test")').getByRole("button", { name: "Возврат" }).click();
};

const openQueue = async (page: Page): Promise<void> => {
  await button(page, "Очередь abuse").click();
};

const openAudit = async (page: Page): Promise<void> => {
  await openQueue(page);
  await page.locator('[aria-label="Открыть аудит abuser@parity.test"]').click();
};

export const ADMIN_FINANCE_STATES: readonly State[] = [
  finance("populated", text("declined@parity.test"), { scope: "full" }),
  finance("acquiring.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/payments/routing")] }),
  finance("acquiring.scope-closed", text("оплата недоступна"), {
    overrides: [reply("GET", "/v1/admin/payments/routing", 200, FX_CLOSED, "в засеве для валюты включены lava.top")],
  }),
  finance("acquiring.dirty", () => 'button:has-text("Применить")', {
    act: async (page) => page.locator('[aria-label="Включить lava.top — карта"]').first().click(),
  }),
  finance("tx.loading", () => "svg.spin", { reveal: true, overrides: [hold("GET", TRANSACTIONS)] }),
  finance("tx.empty", text("Транзакций пока нет."), {
    reveal: true,
    overrides: [reply("GET", TRANSACTIONS, 200, [], "в засеве есть оплаты")],
  }),
  finance("tx.empty-filtered", text("Транзакций с таким статусом нет."), {
    reveal: true,
    overrides: [{ method: "GET", path: TRANSACTIONS, reason: "в засеве есть возврат", respond: ["recorded", { status: 200, body: [] }] }],
    act: async (page) => choose(page, "Все статусы", "Возвраты"),
  }),
  finance("tx.filter", () => 'tr:has-text("trusted@parity.test")', {
    reveal: true,
    act: async (page) => choose(page, "Все статусы", "Успешные"),
  }),
  finance("refund-confirm", () => 'dialog[aria-label="Деньги вернули в кабинете эквайера?"]', { act: refund }),
  finance("refund-error-toast", () => '[role=alert]:has-text("Не удалось оформить возврат")', {
    expectsAlert: true,
    overrides: [serverError("POST", "/v1/admin/finance/transactions/{id}/refund")],
    act: refund,
  }),
  finance("user-panel", text("Расходы по моделям"), {
    act: async (page) => page.locator('button[aria-label="Сводка по pro@parity.test"]').first().click(),
  }),
  finance("user-panel.loading", () => "div[role=presentation] svg.spin", {
    overrides: [hold("GET", "/v1/admin/analytics/users/{id}")],
    act: async (page) => page.locator('button[aria-label="Сводка по pro@parity.test"]').first().click(),
  }),

  security("overview.populated", text("6 IP за сутки — возможный шеринг аккаунта"), { scope: "full" }),
  security("overview.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/monitoring")] }),
  security("overview.empty", text("Подозрений на шеринг нет."), {
    overrides: [reply("GET", "/v1/admin/monitoring", 200, { abuse: [], errors: [], abuse_count: 0, errors_last_hour: 0 },
      "в засеве есть шеринг и ошибки")],
  }),
  security("queue.populated", text("score 0.93"), { act: openQueue }),
  security("queue.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/abuse")], act: openQueue }),
  security("queue.empty", text("Очередь пуста — подозрительных аккаунтов нет."), {
    overrides: [reply("GET", "/v1/admin/abuse", 200, { items: [], total: 0, unread: 0 }, "в засеве есть очередь abuse")],
    act: openQueue,
  }),
  security("audit.populated", text("route_cheap → flagged"), { act: openAudit }),
  security("audit.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/abuse/{id}")], act: openAudit }),
  security("audit.no-events", text("Событий не зафиксировано."), {
    overrides: [merged("GET", "/v1/admin/abuse/{id}", { events: [] }, "у засеянного пользователя есть история")],
    act: openAudit,
  }),
  security("audit.no-data", text("Нет данных по пользователю."), {
    overrides: [reply("GET", "/v1/admin/abuse/{id}", 404, { detail: "not_found" }, "пользователь ушёл из очереди после её загрузки")],
    act: openAudit,
  }),
  { id: "admin.security.audit.no-user", fixture: "admin/security", url: "/app/admin/security?tab=audit", scope: "single",
    languages: RU, marker: text("Выберите пользователя") },
];
