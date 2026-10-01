// Визиты входа, регистрации, сброса пароля и подключения десктопа.
// Состояния — parity/inventory/shell-auth-account-billing.md, разделы /login,
// /register, /reset-password, /connect.

import { ORIGIN } from "../../config.ts";
import { exactText, withText, type Translate } from "../../i18n/texts.ts";
import {
  ALERT,
  NEW_PASSWORD,
  PERSONA_PASSWORD,
  startRegistration,
  STATUS,
  submitLogin,
  WRONG_PASSWORD,
} from "../../ui/draft-ui.ts";
import type { Visit } from "./types.ts";

const loginTitle = (t: Translate): string => withText("h1", t("auth:titleLogin"));

export const AUTH_VISITS: readonly Visit[] = [
  // Набор кнопок соцвхода черновик выбирает по стране и языку: русский язык или
  // страна RU — Яндекс и VK; иначе Google и GitHub.
  { id: "auth/login", persona: null, url: "/app/login", marker: loginTitle },
  {
    id: "auth/login-world",
    persona: null,
    url: "/app/login",
    marker: () => "a[href*='/v1/auth/social/github/start']",
    country: "US",
    languages: ["en"],
  },
  {
    id: "auth/login-invalid",
    persona: null,
    url: "/app/login",
    marker: (t) => withText(ALERT, t("errors:invalid_credentials")),
    act: (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD),
  },
  {
    id: "auth/login-banned",
    persona: null,
    url: "/app/login",
    marker: (t) => withText(ALERT, t("errors:account_banned")),
    act: (page) => submitLogin(page, "banned@parity.test", PERSONA_PASSWORD),
  },
  { id: "auth/register", persona: null, url: "/app/register", marker: (t) => withText("h1", t("auth:titleRegister")) },
  {
    id: "auth/register-verify",
    persona: null,
    url: "/app/register",
    marker: (t) => withText(ALERT, t("errors:invalid_code")),
    mutates: true,
    languages: ["ru"],
    act: async (page, context) => {
      await startRegistration(page, context.t, "register@parity.test");
      await page.locator("input[autocomplete=one-time-code]").fill("000000");
      await page.locator("button[type=submit]:enabled").click();
    },
  },
  {
    // Заявка на регистрацию живёт в Redis до ввода кода; вход тем же паролем
    // черновик возвращает на экран кода (403 email_not_verified).
    id: "auth/login-unverified",
    persona: null,
    url: "/app/register",
    marker: (t) => withText("h1", t("auth:titleVerify")),
    mutates: true,
    act: async (page, context) => {
      const email = `unverified-${context.language}@parity.test`;
      await startRegistration(page, context.t, email);
      await page.goto(`${ORIGIN}/app/login`);
      await submitLogin(page, email, NEW_PASSWORD);
      await page.locator(STATUS).first().waitFor();
    },
  },
  {
    id: "auth/forgot",
    persona: null,
    url: "/app/login",
    marker: (t) => withText(STATUS, t("auth:resetLinkSent")),
    act: async (page, { t }) => {
      await page.getByText(t("auth:forgotLink")).click();
      await page.locator("input[type=email]").fill("free@parity.test");
      await page.locator("button[type=submit]:enabled").click();
    },
  },
  {
    id: "auth/reset-invalid",
    persona: null,
    url: "/app/reset-password?token=parity-invalid-token",
    marker: (t) => withText(ALERT, t("errors:reset_token_invalid")),
    act: async (page) => {
      const fields = page.locator("input[type=password]");
      await fields.nth(0).fill(NEW_PASSWORD);
      await fields.nth(1).fill(NEW_PASSWORD);
      await page.locator("button[type=submit]:enabled").click();
    },
  },
  {
    id: "auth/connect-anonymous",
    persona: null,
    url: "/app/connect?state=parity-state",
    marker: (t) => exactText(t("auth:connect.title")),
  },
  { id: "auth/connect", persona: "free", url: "/app/connect?state=parity-state", marker: (t) => exactText(t("auth:connect.doneTitle")) },
];
