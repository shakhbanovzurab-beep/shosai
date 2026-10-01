// Визиты входа, регистрации, сброса пароля и подключения десктопа.
// Состояния — parity/inventory/shell-auth-account-billing.md, разделы /login,
// /register, /reset-password, /connect.

import type { Page } from "@playwright/test";

import { ORIGIN } from "../../config.ts";
import type { Visit } from "./types.ts";

const WRONG_PASSWORD = "wrong-password-1";
const PERSONA_PASSWORD = "parity-password-1";
/** Пароль новых регистраций: проходит все правила надёжности черновика. */
const NEW_PASSWORD = "Parity-password-2";

async function submitLogin(page: Page, email: string, password: string): Promise<void> {
  await page.locator("input[type=email]").fill(email);
  await page.locator("input[type=password]").fill(password);
  await page.locator("button[type=submit]:enabled").click();
}

async function startRegistration(page: Page, email: string): Promise<void> {
  await page.locator("input[placeholder='Имя']").fill("Лев Новиков");
  await page.locator("input[type=email]").fill(email);
  await page.locator("input[type=password]").fill(NEW_PASSWORD);
  await page.locator("form input[type=checkbox]").first().check();
  await page.locator("button[type=submit]:enabled").click();
  await page.locator("h1:has-text('Почти всё')").waitFor();
}

export const AUTH_VISITS: readonly Visit[] = [
  // Набор кнопок соцвхода черновик выбирает по стране и языку: русский язык или
  // страна RU — Яндекс и VK; иначе Google и GitHub.
  { id: "auth/login", persona: null, url: "/app/login", marker: "h1:has-text('Привет!')" },
  {
    id: "auth/login-world",
    persona: null,
    url: "/app/login",
    marker: "a[href*='/v1/auth/social/github/start']",
    country: "US",
    language: "en",
  },
  {
    id: "auth/login-invalid",
    persona: null,
    url: "/app/login",
    marker: "[role=alert]:has-text('Неверный email или пароль')",
    act: (page) => submitLogin(page, "free@parity.test", WRONG_PASSWORD),
  },
  {
    id: "auth/login-banned",
    persona: null,
    url: "/app/login",
    marker: "[role=alert]:has-text('Аккаунт заблокирован')",
    act: (page) => submitLogin(page, "banned@parity.test", PERSONA_PASSWORD),
  },
  { id: "auth/register", persona: null, url: "/app/register", marker: "h1:has-text('Знакомимся')" },
  {
    id: "auth/register-verify",
    persona: null,
    url: "/app/register",
    marker: "[role=alert]:has-text('Неверный или истёкший код')",
    mutates: true,
    act: async (page) => {
      await startRegistration(page, "register@parity.test");
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
    marker: "[role=status]:has-text('Подтвердите email')",
    mutates: true,
    act: async (page) => {
      await startRegistration(page, "unverified@parity.test");
      await page.goto(`${ORIGIN}/app/login`);
      await submitLogin(page, "unverified@parity.test", NEW_PASSWORD);
    },
  },
  {
    id: "auth/forgot",
    persona: null,
    url: "/app/login",
    marker: "[role=status]:has-text('Инструкции по восстановлению доступа')",
    act: async (page) => {
      await page.getByText("Забыли пароль?").click();
      await page.locator("input[type=email]").fill("free@parity.test");
      await page.locator("button[type=submit]:enabled").click();
    },
  },
  {
    id: "auth/reset-invalid",
    persona: null,
    url: "/app/reset-password?token=parity-invalid-token",
    marker: "[role=alert]:has-text('Ссылка сброса недействительна или истекла')",
    act: async (page) => {
      const fields = page.locator("input[type=password]");
      await fields.nth(0).fill(NEW_PASSWORD);
      await fields.nth(1).fill(NEW_PASSWORD);
      await page.locator("button[type=submit]:enabled").click();
    },
  },
  { id: "auth/connect-anonymous", persona: null, url: "/app/connect?state=parity-state", marker: "text=Подключение приложения" },
  { id: "auth/connect", persona: "free", url: "/app/connect?state=parity-state", marker: "text=Готово!" },
];
