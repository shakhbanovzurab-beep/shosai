// Состояния входа, регистрации, сброса пароля и подключения десктопа.
// Инвентарь: parity/inventory/shell-auth-account-billing.md.

import { ORIGIN } from "../config.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { NEW_PASSWORD, PERSONA_PASSWORD, startRegistration, STATUS, submitLogin, WRONG_PASSWORD } from "../ui/draft-ui.ts";
import { alert, countdownMask, loginTitle } from "./common.ts";
import { hold, rateLimited, reply, serverError } from "./overrides.ts";
import type { State } from "./types.ts";

const LOGIN = "/v1/auth/login";

/** Пароль, на котором индикатор надёжности показывает свой уровень. */
function strength(level: string, password: string, label: (t: Translate) => string): State {
  return {
    id: `auth.register.pw-${level}`,
    fixture: "auth/register",
    scope: "single",
    act: async (page) => page.locator("input[type=password]").fill(password),
    marker: (t) => exactText(label(t)),
  };
}

export const AUTH_STATES: readonly State[] = [
  { id: "auth.login.default", fixture: "auth/login", scope: "full", marker: loginTitle },
  {
    id: "auth.login.password-revealed",
    fixture: "auth/login",
    scope: "single",
    act: async (page, { t }) => {
      await page.locator("input[type=password]").fill(PERSONA_PASSWORD);
      await page.getByRole("button", { name: t("common:input.showPassword") }).click();
    },
    marker: (t) => `button[aria-label=${JSON.stringify(t("common:input.hidePassword"))}]`,
  },
  {
    id: "auth.login.submitting",
    fixture: "auth/login",
    scope: "single",
    overrides: [hold("POST", LOGIN)],
    act: async (page) => submitLogin(page, "free@parity.test", PERSONA_PASSWORD),
    marker: (t) => withText("button[type=submit]", t("auth:signingIn")),
  },
  {
    id: "auth.login.error-invalid",
    fixture: "auth/login-invalid",
    scope: "full",
    expectsAlert: true,
    act: async (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD),
    marker: alert((t) => t("errors:invalid_credentials")),
  },
  {
    id: "auth.login.error-banned",
    fixture: "auth/login-banned",
    scope: "single",
    expectsAlert: true,
    act: async (page) => submitLogin(page, "banned@parity.test", PERSONA_PASSWORD),
    marker: alert((t) => t("errors:account_banned")),
  },
  {
    id: "auth.login.error-captcha",
    fixture: "auth/login-invalid",
    scope: "single",
    expectsAlert: true,
    overrides: [
      reply("POST", LOGIN, 400, { detail: "captcha_failed" }, "капча на стенде записи выключена; ответ — api/auth.py черновика"),
    ],
    act: async (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD),
    marker: alert((t) => t("errors:captcha_failed")),
  },
  {
    id: "auth.login.error-rate-limited",
    fixture: "auth/login-invalid",
    scope: "single",
    expectsAlert: true,
    overrides: [rateLimited("POST", LOGIN, "5 per 1 minute")],
    act: async (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD),
    marker: alert((t) => t("errors:rate_limited")),
  },
  {
    id: "auth.login.error-server",
    fixture: "auth/login-invalid",
    scope: "single",
    expectsAlert: true,
    overrides: [
      serverError("POST", LOGIN),
    ],
    act: async (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD),
    marker: alert((t) => t("errors:server_error")),
  },
  {
    id: "auth.login.social-world",
    fixture: "auth/login-world",
    scope: "full",
    languages: ["en"],
    marker: () => "a[href*='/v1/auth/social/github/start']",
  },
  {
    id: "auth.login.unverified",
    fixture: "auth/login-unverified",
    scope: "full",
    mask: countdownMask,
    act: async (page, { language, t }) => {
      const email = `unverified-${language}@parity.test`;
      await startRegistration(page, t, email);
      await page.goto(`${ORIGIN}/app/login`);
      await submitLogin(page, email, NEW_PASSWORD);
      await page.locator(STATUS).first().waitFor();
    },
    marker: (t) => withText("h1", t("auth:titleVerify")),
  },
  { id: "auth.register.default", fixture: "auth/register", scope: "full", marker: (t) => withText("h1", t("auth:titleRegister")) },
  strength("weak", "abc", (t) => t("auth:pwStrength.weak")),
  strength("fair", "Abcdefgh", (t) => t("auth:pwStrength.fair")),
  strength("good", "Abcdefg1", (t) => t("auth:pwStrength.good")),
  strength("strong", "Abcdef1!", (t) => t("auth:pwStrength.strong")),
  {
    id: "auth.verify.error",
    fixture: "auth/register-verify",
    scope: "single",
    expectsAlert: true,
    mask: countdownMask,
    act: async (page, { t }) => {
      await startRegistration(page, t, "register@parity.test");
      await page.locator("input[autocomplete=one-time-code]").fill("000000");
      await page.locator("button[type=submit]:enabled").click();
    },
    marker: alert((t) => t("errors:invalid_code")),
  },
  {
    id: "auth.forgot.sent",
    fixture: "auth/forgot",
    scope: "full",
    act: async (page, { t }) => {
      await page.getByText(t("auth:forgotLink")).click();
      await page.locator("input[type=email]").fill("free@parity.test");
      await page.locator("button[type=submit]:enabled").click();
    },
    marker: (t) => withText(STATUS, t("auth:resetLinkSent")),
  },
  {
    id: "auth.reset.default",
    fixture: "auth/reset-invalid",
    scope: "full",
    marker: (t) => exactText(t("auth:newPasswordTitle")),
  },
  {
    id: "auth.reset.error-token",
    fixture: "auth/reset-invalid",
    scope: "single",
    expectsAlert: true,
    act: async (page) => {
      const fields = page.locator("input[type=password]");
      await fields.nth(0).fill(NEW_PASSWORD);
      await fields.nth(1).fill(NEW_PASSWORD);
      await page.locator("button[type=submit]:enabled").click();
    },
    marker: alert((t) => t("errors:reset_token_invalid")),
  },
  { id: "auth.connect.anonymous", fixture: "auth/connect-anonymous", scope: "full", marker: (t) => exactText(t("auth:connect.title")) },
  { id: "auth.connect.done", fixture: "auth/connect", scope: "full", marker: (t) => exactText(t("auth:connect.doneTitle")) },
];
