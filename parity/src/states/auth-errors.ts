// Варианты ошибок и ожидания на экранах входа и регистрации (шаг 3b).
// Мелкие вариации — одна ячейка; синтетика — переопределения с причиной.

import { withText } from "../i18n/texts.ts";
import { NEW_PASSWORD, PERSONA_PASSWORD, submitLogin, submitRegistration, WRONG_PASSWORD } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { guestRefresh, hold, networkFailure, reply, validationError } from "./overrides.ts";
import type { State } from "./types.ts";

const LOGIN = "/v1/auth/login";
const REGISTER = "/v1/auth/register";

const wrongLogin: State["act"] = async (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD);

export const AUTH_ERROR_STATES: readonly State[] = [
  {
    id: "auth.login.error-validation",
    fixture: "auth/login-invalid",
    scope: "single",
    expectsAlert: true,
    overrides: [validationError("POST", LOGIN, "password")],
    act: wrongLogin,
    marker: alert((t) => t("errors:validation_error")),
  },
  {
    id: "auth.login.error-generic",
    fixture: "auth/login-invalid",
    scope: "single",
    expectsAlert: true,
    overrides: [reply("POST", LOGIN, 400, { detail: "unexpected" }, "код ошибки, которого фронтенд не знает: падение на общий текст")],
    act: wrongLogin,
    marker: alert((t) => t("errors:login_failed")),
  },
  {
    id: "auth.login.error-network",
    fixture: "auth/login-invalid",
    scope: "single",
    expectsAlert: true,
    overrides: [networkFailure("POST", LOGIN)],
    act: wrongLogin,
    marker: alert((t) => t("errors:connection_lost")),
  },
  {
    id: "auth.login.ready",
    fixture: "auth/login",
    scope: "single",
    act: async (page) => {
      await page.locator("input[type=email]").fill("free@parity.test");
      await page.locator("input[type=password]").fill(PERSONA_PASSWORD);
    },
    marker: () => "form button[type=submit]:enabled",
  },
  {
    // Возврат от провайдера с билетом, который сервер уже не принимает.
    id: "auth.login.social-return-failed",
    fixture: "auth/login",
    url: "/app/login?social=parity-ticket",
    scope: "single",
    expectsAlert: true,
    overrides: [
      reply("POST", "/v1/auth/social/complete", 401, { detail: "social_state_invalid" }, "билет входа выдаёт провайдер; ответ — identity/channels/http.py черновика"),
      guestRefresh(),
    ],
    marker: alert((t) => t("auth:socialFailed")),
  },
  {
    id: "auth.login.lang-menu",
    fixture: "auth/login",
    scope: "single",
    act: async (page, { t }) => page.getByRole("button", { name: t("common:language.label") }).click(),
    // Название языка на нём самом — значение, а не перевод.
    marker: () => 'button[aria-pressed=true]:has-text("Русский")',
  },
  {
    id: "auth.login.social-tip",
    fixture: "auth/login",
    scope: "single",
    // Фокусом, а не наведением: перед снимком указатель уходит в угол, и
    // подсказка по наведению закрылась бы.
    act: async (page, { t }) => page.getByRole("button", { name: t("auth:socialLegalNote") }).focus(),
    marker: () => "[role=tooltip]",
  },
  {
    id: "auth.login.social-return-error",
    fixture: "auth/login",
    url: "/app/login?social_error=social_state_invalid",
    scope: "single",
    expectsAlert: true,
    marker: alert((t) => t("auth:socialError.social_state_invalid")),
  },
  {
    id: "auth.register.error-email-invalid",
    fixture: "auth/register",
    scope: "single",
    expectsAlert: true,
    // Адрес проходит проверку браузера (type=email), но не проверку черновика:
    // без точки в домене. «not-an-email» браузер не дал бы отправить вовсе.
    act: async (page, { t }) => submitRegistration(page, t, "lev@parity"),
    marker: alert((t) => t("errors:email_invalid")),
  },
  {
    id: "auth.register.error-password-short",
    fixture: "auth/register",
    scope: "single",
    expectsAlert: true,
    act: async (page, { t }) => submitRegistration(page, t, "short@parity.test", "Abc1!"),
    marker: alert((t) => t("errors:password_too_short")),
  },
  {
    id: "auth.register.submitting",
    fixture: "auth/register",
    scope: "single",
    overrides: [hold("POST", REGISTER)],
    act: async (page, { t }) => submitRegistration(page, t, "waiting@parity.test", NEW_PASSWORD),
    marker: (t) => withText("button[type=submit]", t("auth:creating")),
  },
  {
    id: "auth.register.error-email-taken",
    fixture: "auth/register",
    scope: "single",
    expectsAlert: true,
    overrides: [
      reply("POST", REGISTER, 400, { detail: "Email already registered" }, "занятый адрес; текст ответа — api/auth.py черновика"),
    ],
    act: async (page, { t }) => submitRegistration(page, t, "free@parity.test"),
    marker: alert((t) => t("errors:email_taken")),
  },
  {
    id: "auth.register.error-generic",
    fixture: "auth/register",
    scope: "single",
    expectsAlert: true,
    overrides: [reply("POST", REGISTER, 400, { detail: "unexpected" }, "код ошибки, которого фронтенд не знает")],
    act: async (page, { t }) => submitRegistration(page, t, "other@parity.test"),
    marker: alert((t) => t("errors:register_failed")),
  },
  {
    id: "auth.register.ready",
    fixture: "auth/register",
    scope: "single",
    act: async (page, { t }) => {
      await page.locator(`input[placeholder=${JSON.stringify(t("auth:namePlaceholder"))}]`).fill("Лев Новиков");
      await page.locator("input[type=email]").fill("ready@parity.test");
      await page.locator("input[type=password]").fill(NEW_PASSWORD);
      await page.locator("form input[type=checkbox]").first().check();
    },
    marker: () => "form button[type=submit]:enabled",
  },
];
