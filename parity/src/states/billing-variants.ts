// Варианты вкладки «Подписка» (шаг 3b): загрузка и отсутствие подписки, проблемы
// продления, выбор оплаты, промокоды, начало оплаты. Вкладка «Оплата» —
// billing-cards.ts.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog, STATUS } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const AUTO_RENEW = "/v1/me/billing/auto-renew";
const CHECKOUT = "/v1/me/billing/checkout";

/** Подстановка, которую фронтенд форматирует сам (даты, деньги): маркер — текст до неё. */
const SLOT = "\u0000";
const before = (text: string): string => text.split(SLOT)[0] ?? text;

/** Автопродление Pro по сохранённой карте — как в записи, но с проблемой продления. */
function renewalIssue(kind: string, inGrace: boolean): JsonValue {
  return {
    eligible: true,
    enabled: kind !== "exhausted",
    renewal_provider: kind === "awaiting_acquirer" ? "lava" : null,
    method: kind === "awaiting_acquirer" ? null : { mask: "4242", exp: "12/2027", brand: "visa" },
    next_charge: null,
    issue: {
      kind,
      access_until: kind === "exhausted" ? null : inGrace ? "2026-07-20T12:00:00Z" : "2026-08-10T12:00:00Z",
      next_attempt_at: kind === "declined" ? "2026-07-18T12:00:00Z" : null,
      in_grace: inGrace,
    },
  };
}

function issueState(id: string, kind: string, inGrace: boolean, marker: (t: Translate) => string): State {
  return {
    id,
    fixture: "billing/subscription-pro",
    scope: "single",
    overrides: [
      reply("GET", AUTO_RENEW, 200, renewalIssue(kind, inGrace), "проблему продления создаёт эквайер; стенд записи без эквайера"),
    ],
    marker: (t) => `${cabinetDialog(t)} >> ${withText(STATUS, marker(t))}`,
  };
}

/** Первая карточка с оплатой — Start: у Free кнопки оплаты нет. */
async function enterPromo(page: Page, { t }: StateContext, code: string): Promise<void> {
  const field = page.locator(`input[placeholder=${JSON.stringify(t("billing:cab.promoPlaceholder"))}]`).first();
  await field.fill(code);
  await field.press("Tab");
}

function promoState(id: string, code: string, body: JsonValue, marker: (t: Translate) => string): State {
  return {
    id: `billing.promo.${id}`,
    fixture: "billing/subscription-free",
    scope: "single",
    overrides: [reply("POST", "/v1/me/billing/promo-check", 200, body, "промокоды заводит администратор; в засеве их нет")],
    act: async (page, context) => enterPromo(page, context, code),
    marker: (t) => withText(cabinetDialog(t), marker(t)),
  };
}

const promoBase = { currency: "RUB", discount: 0, discount_rub: 0 };

async function startCheckout(page: Page, { t }: StateContext): Promise<void> {
  await page.locator(cabinetDialog(t)).getByRole("button", { name: t("billing:cab.goPay") }).first().click();
}

const freeQuota = { unlimited: false, limit_minutes: 60, bonus_minutes: 0, used_minutes: 12, remaining_minutes: 48, exhausted: false };
const noUsage = { session_count: 0, minutes_used: 0, ai_questions: 0, total_tokens: 0 };

export const BILLING_VARIANT_STATES: readonly State[] = [
  {
    id: "billing.subscription.loading",
    fixture: "billing/subscription-free",
    scope: "single",
    overrides: [hold("GET", "/v1/me")],
    marker: (t) => `${cabinetDialog(t)} svg.spin`,
  },
  {
    id: "billing.subscription.none",
    fixture: "billing/subscription-free",
    scope: "single",
    overrides: [
      reply("GET", "/v1/me", 200, { subscription: null, usage: noUsage, quota: freeQuota }, "аккаунт без подписки засев не создаёт: Free выдаётся при регистрации"),
    ],
    marker: (t) => exactText(t("billing:cab.noSubscription")),
  },
  issueState("billing.issue.declined", "declined", false, (t) => before(t("billing:cab.billing.issueDeclined", { until: SLOT, retry: SLOT }))),
  issueState("billing.subscription.grace", "declined", true, (t) => before(t("billing:cab.billing.issueDeclined", { until: SLOT, retry: SLOT }))),
  issueState("billing.issue.processing", "processing", false, (t) => before(t("billing:cab.billing.issueProcessing", { until: SLOT }))),
  issueState("billing.issue.awaiting", "awaiting_acquirer", false, (t) => before(t("billing:cab.billing.issueAwaiting", { until: SLOT }))),
  issueState("billing.issue.exhausted", "exhausted", false, (t) => t("billing:cab.billing.issueExhausted")),
  {
    id: "billing.upgrade.unavailable",
    fixture: "billing/subscription-free",
    scope: "single",
    overrides: [reply("GET", "/v1/me/billing/methods", 200, { currency: "RUB", methods: [] }, "эквайринг выключен: стенд записи держит его включённым")],
    marker: (t) => exactText(t("billing:cab.payUnavailable")),
  },
  promoState("invalid", "NOPE", { ...promoBase, valid: false, kind: null, value: null }, (t) => t("billing:cab.promoInvalid")),
  promoState("percent", "SALE10", { ...promoBase, valid: true, kind: "percent", value: 10, discount_rub: 79, discount: 79 }, (t) =>
    before(t("billing:cab.promoPercent", { value: 10, discount: SLOT })),
  ),
  promoState("days", "WEEK7", { ...promoBase, valid: true, kind: "bonus_days", value: 7 }, (t) => t("billing:cab.promoDays", { value: 7 })),
  promoState("affiliate", "BLOGGER", { ...promoBase, valid: true, kind: "affiliate", value: null }, (t) => t("billing:cab.promoAffiliate")),
  {
    id: "billing.checkout.preparing",
    fixture: "billing/subscription-free",
    scope: "single",
    overrides: [hold("POST", CHECKOUT)],
    act: startCheckout,
    marker: (t) => withText("button", t("billing:cab.preparingPay")),
  },
  {
    id: "billing.checkout.error",
    fixture: "billing/subscription-free",
    scope: "single",
    expectsAlert: true,
    overrides: [serverError("POST", CHECKOUT)],
    act: startCheckout,
    marker: alert((t) => t("billing:cab.payError")),
  },
  {
    id: "billing.checkout.already-done",
    fixture: "billing/subscription-free",
    scope: "single",
    overrides: [
      reply("POST", CHECKOUT, 409, { detail: "payment_already_completed" }, "сверка с эквайером нашла прошлую оплату; ответ — api/me_billing.py черновика"),
    ],
    act: startCheckout,
    marker: (t) => withText(STATUS, t("billing:cab.payAlreadyDone")),
  },
];
