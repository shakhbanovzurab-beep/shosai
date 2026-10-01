// Сценарии вне формы входа (шаг 3b): подтверждение кода, восстановление и сброс
// пароля, подключение десктопа, согласие при первом входе через соцсеть.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { ALERT, startRegistration } from "../ui/draft-ui.ts";
import { alert, countdownMask } from "./common.ts";
import { guestRefresh, hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const FORGOT = "/v1/auth/forgot-password";
const RESET = "/v1/auth/reset-password";
const DESKTOP_CODE = "/v1/auth/desktop/code";
const VERIFY = "/v1/auth/verify-email";
const CONSENT = "/v1/auth/social/consent";
const CONSENT_URL = "/app/login?social_consent=parity-ticket&social_provider=yandex";

/** Экран кода после регистрации; адрес у каждого языка свой, как в записи. */
async function toVerify(page: Page, { language, t }: StateContext): Promise<void> {
  await startRegistration(page, t, `unverified-${language}@parity.test`);
}

async function enterCode(page: Page, context: StateContext): Promise<void> {
  await toVerify(page, context);
  await page.locator("input[autocomplete=one-time-code]").fill("123456");
}

async function openForgot(page: Page, { t }: StateContext): Promise<void> {
  await page.getByText(t("auth:forgotLink")).click();
  await page.locator("input[type=email]").fill("free@parity.test");
}

async function fillReset(page: Page, first: string, second: string): Promise<void> {
  const fields = page.locator("input[type=password]");
  await fields.nth(0).fill(first);
  await fields.nth(1).fill(second);
  await page.locator("button[type=submit]:enabled").click();
}

const pending = reply(
  "GET",
  "/v1/auth/social/pending",
  200,
  { provider: "yandex", email: "ivan@ya.ru" },
  "заявка на вход через соцсеть рождается у провайдера; стенд до него не достаёт",
);
const consentTitle = (t: Translate): string => withText("h1", t("auth:titleSocialConsent"));

/** Согласие на обработку данных и кнопка «Создать аккаунт». */
async function submitConsent(page: Page, { t }: StateContext): Promise<void> {
  await page.locator("form input[type=checkbox]").first().check();
  await page.getByRole("button", { name: t("auth:socialConsentBtn") }).click();
}

export const AUTH_FLOW_STATES: readonly State[] = [
  {
    id: "auth.verify.default",
    fixture: "auth/login-unverified",
    scope: "full",
    mask: countdownMask,
    act: toVerify,
    marker: (t) => withText("h1", t("auth:titleVerify")),
  },
  {
    id: "auth.verify.code-entered",
    fixture: "auth/login-unverified",
    scope: "single",
    mask: countdownMask,
    act: enterCode,
    marker: () => "form button[type=submit]:enabled",
  },
  {
    id: "auth.verify.submitting",
    fixture: "auth/login-unverified",
    scope: "single",
    mask: countdownMask,
    overrides: [hold("POST", VERIFY)],
    act: async (page, context) => {
      await enterCode(page, context);
      await page.locator("button[type=submit]:enabled").click();
    },
    marker: (t) => withText("button[type=submit]", t("auth:checking")),
  },
  {
    id: "auth.forgot.default",
    fixture: "auth/forgot",
    scope: "full",
    act: async (page, { t }) => page.getByText(t("auth:forgotLink")).click(),
    marker: (t) => withText("h1", t("auth:titleForgot")),
  },
  {
    id: "auth.forgot.sending",
    fixture: "auth/forgot",
    scope: "single",
    overrides: [hold("POST", FORGOT)],
    act: async (page, context) => {
      await openForgot(page, context);
      await page.locator("button[type=submit]:enabled").click();
    },
    marker: (t) => withText("button[type=submit]", t("auth:sending")),
  },
  {
    id: "auth.forgot.error",
    fixture: "auth/forgot",
    scope: "single",
    expectsAlert: true,
    overrides: [serverError("POST", FORGOT)],
    act: async (page, context) => {
      await openForgot(page, context);
      await page.locator("button[type=submit]:enabled").click();
    },
    marker: alert((t) => t("errors:server_error")),
  },
  {
    id: "auth.reset.no-token",
    fixture: "auth/reset-invalid",
    url: "/app/reset-password",
    scope: "full",
    marker: (t) => exactText(t("auth:tokenMissing")),
  },
  {
    id: "auth.reset.error-short",
    fixture: "auth/reset-invalid",
    scope: "single",
    expectsAlert: true,
    act: async (page) => fillReset(page, "Abc1!xy", "Abc1!xy"),
    marker: (t) => withText(ALERT, t("auth:passwordTooShort")),
  },
  {
    id: "auth.reset.error-mismatch",
    fixture: "auth/reset-invalid",
    scope: "single",
    expectsAlert: true,
    act: async (page) => fillReset(page, "Parity-password-2", "Parity-password-3"),
    marker: (t) => withText(ALERT, t("auth:passwordsMismatch")),
  },
  {
    id: "auth.reset.saving",
    fixture: "auth/reset-invalid",
    scope: "single",
    overrides: [hold("POST", RESET)],
    act: async (page) => fillReset(page, "Parity-password-2", "Parity-password-2"),
    marker: (t) => withText("button[type=submit]", t("auth:saving")),
  },
  {
    id: "auth.connect.working",
    fixture: "auth/connect",
    scope: "single",
    overrides: [hold("POST", DESKTOP_CODE)],
    marker: (t) => exactText(t("auth:connect.connecting")),
  },
  {
    id: "auth.connect.error",
    fixture: "auth/connect",
    scope: "single",
    overrides: [serverError("POST", DESKTOP_CODE)],
    marker: (t) => exactText(t("auth:connect.failTitle")),
  },
  { id: "auth.social-consent.default", fixture: "auth/login", url: CONSENT_URL, scope: "full", overrides: [pending], marker: consentTitle },
  {
    id: "auth.social-consent.checked",
    fixture: "auth/login",
    url: CONSENT_URL,
    scope: "single",
    overrides: [pending],
    act: async (page) => page.locator("form input[type=checkbox]").first().check(),
    marker: (t) => withText("button:enabled", t("auth:socialConsentBtn")),
  },
  {
    id: "auth.social-consent.submitting",
    fixture: "auth/login",
    url: CONSENT_URL,
    scope: "single",
    overrides: [pending, hold("POST", CONSENT)],
    act: submitConsent,
    marker: (t) => withText("button", t("auth:creating")),
  },
  {
    id: "auth.social-consent.error",
    fixture: "auth/login",
    url: CONSENT_URL,
    scope: "single",
    expectsAlert: true,
    overrides: [
      pending,
      reply("POST", CONSENT, 401, { detail: "social_state_invalid" }, "билет согласия истёк; ответ — identity/channels/http.py черновика"),
      guestRefresh(),
    ],
    act: submitConsent,
    marker: alert((t) => t("auth:socialError.social_state_invalid")),
  },
];
