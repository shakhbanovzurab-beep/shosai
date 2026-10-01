// Варианты вкладки «Оплата» (шаг 3b): загрузка, карта не сохранена,
// автопродление выключено, смена карты и её отказы.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const AUTO_RENEW = "/v1/me/billing/auto-renew";
const BINDING = "/v1/me/billing/payment-method/binding";
const BINDING_ID = "00000000-0000-4000-8000-000000000201";
const CARD = { mask: "4242", exp: "12/2027", brand: "visa" };

/** Автопродление в форме ответа черновика `GET /v1/me/billing/auto-renew`. */
function renewal(enabled: boolean, method: JsonValue): JsonValue {
  return { eligible: true, enabled, renewal_provider: null, method, next_charge: null, issue: null };
}

async function changeCard(page: Page, { t }: StateContext): Promise<void> {
  await page.locator(cabinetDialog(t)).getByRole("button", { name: t("billing:cab.billing.changeCard") }).click();
}

const cardSheet = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("billing:cab.billing.cardSheetTitle"))}]`;

/** Отказ начать смену карты: тост с текстом по коду ответа. */
function bindingRefused(id: string, status: number, code: string, key: (t: Translate) => string): State {
  return {
    id: `billing.card-sheet.${id}`,
    fixture: "billing/payments-pro",
    scope: "single",
    expectsAlert: true,
    overrides: [reply("POST", BINDING, status, { detail: code }, "отказ в смене карты; ответ — api/me_billing.py черновика")],
    act: changeCard,
    marker: alert(key),
  };
}

export const BILLING_CARD_STATES: readonly State[] = [
  {
    id: "billing.billing.loading",
    fixture: "billing/payments-pro",
    scope: "single",
    overrides: [hold("GET", AUTO_RENEW)],
    marker: (t) => `${cabinetDialog(t)} svg.spin`,
  },
  {
    id: "billing.billing.no-card",
    fixture: "billing/payments-pro",
    scope: "single",
    overrides: [reply("GET", AUTO_RENEW, 200, renewal(false, null), "карту отвязывает человек; засев держит её привязанной")],
    marker: (t) => exactText(t("billing:cab.billing.noCardHint")),
  },
  {
    id: "billing.renewal.off",
    fixture: "billing/payments-pro",
    scope: "single",
    overrides: [reply("GET", AUTO_RENEW, 200, renewal(false, CARD), "автопродление выключает человек; засев держит его включённым")],
    marker: (t) => exactText(t("billing:cab.billing.offHint")),
  },
  {
    id: "billing.card-sheet.tab",
    fixture: "billing/payments-pro",
    scope: "full",
    overrides: [
      reply(
        "POST",
        BINDING,
        200,
        { binding_id: BINDING_ID, provider: "tbank", payment_url: "https://securepay.tinkoff.ru/new/parity", widget: null, hold_amount: 0, currency: "RUB" },
        "привязку карты открывает эквайер; стенд записи без эквайера",
      ),
      hold("GET", `${BINDING}/${BINDING_ID}`),
    ],
    act: changeCard,
    marker: (t) => withText(cardSheet(t), t("billing:cab.billing.cardOpenForm")),
  },
  bindingRefused("too-many", 429, "too_many_card_bindings", (t) => t("billing:cab.billing.cardTooMany")),
  bindingRefused("not-eligible", 409, "not_eligible", (t) => t("billing:cab.billing.notEligible")),
  {
    id: "billing.card-sheet.unavailable",
    fixture: "billing/payments-pro",
    scope: "single",
    expectsAlert: true,
    overrides: [serverError("POST", BINDING)],
    act: changeCard,
    marker: alert((t) => t("billing:cab.billing.cardUnavailable")),
  },
];
