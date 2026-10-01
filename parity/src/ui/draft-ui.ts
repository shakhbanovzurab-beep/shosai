// Действия и селекторы экранов, общие для визитов записи и состояний съёмки.
// Селекторы опираются на роли, типы полей и тексты переводов — то, что v2
// обязан сохранить, — а не на классы черновика.

import type { Page } from "@playwright/test";

import { withText, type Translate } from "../i18n/texts.ts";

export const ALERT = "[role=alert]";
export const STATUS = "[role=status]";

/** Пароль персон засева (recording/seed/personas.py). */
export const PERSONA_PASSWORD = "parity-password-1";
export const WRONG_PASSWORD = "wrong-password-1";
/** Пароль новых регистраций: проходит все правила надёжности черновика. */
export const NEW_PASSWORD = "Parity-password-2";

export async function submitLogin(page: Page, email: string, password: string): Promise<void> {
  await page.locator("input[type=email]").fill(email);
  await page.locator("input[type=password]").fill(password);
  await page.locator("button[type=submit]:enabled").click();
}

/** Заполняет форму регистрации и отправляет её; ответ — забота вызывающего. */
export async function submitRegistration(page: Page, t: Translate, email: string, password = NEW_PASSWORD): Promise<void> {
  await page.locator(`input[placeholder=${JSON.stringify(t("auth:namePlaceholder"))}]`).fill("Лев Новиков");
  await page.locator("input[type=email]").fill(email);
  await page.locator("input[type=password]").fill(password);
  await page.locator("form input[type=checkbox]").first().check();
  await page.locator("button[type=submit]:enabled").click();
}

/** Регистрация до экрана ввода кода. */
export async function startRegistration(page: Page, t: Translate, email: string): Promise<void> {
  await submitRegistration(page, t, email);
  await page.locator(withText("h1", t("auth:titleVerify"))).waitFor();
}

/** Окно кабинета: `dialog` с подписью «Личный кабинет» на языке экрана. */
export function cabinetDialog(t: Translate): string {
  return `dialog[aria-label=${JSON.stringify(t("account:cab.title"))}]`;
}

/**
 * Кнопка повторной отправки кода — первая кнопка формы после поля кода: её
 * подпись — обратный отсчёт по настоящим часам. «Назад ко входу» дальше не тикает.
 */
export const RESEND_COUNTDOWN = "form button[type=button] >> nth=0";
