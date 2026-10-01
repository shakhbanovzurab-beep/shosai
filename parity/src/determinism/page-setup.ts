// Подготовка страницы до первого скрипта приложения: localStorage, генератор
// случайных чисел с фиксированным зерном и заглушка капчи.
//
// Функция `setUpPage` выполняется в браузере и сериализуется Playwright, поэтому
// она самодостаточна: никаких замыканий и импортов.

import type { BrowserContext } from "@playwright/test";

export interface PageSetup {
  /** Ключи localStorage: сессия (wh-auth), тема (wh.theme), язык (wh.lang). */
  readonly storage: Readonly<Record<string, string>>;
  /** Зерно Math.random: случайный выбор на экране (подсказка дня) повторяется. */
  readonly randomSeed: number;
}

function setUpPage(setup: PageSetup): void {
  for (const [key, value] of Object.entries(setup.storage)) {
    window.localStorage.setItem(key, value);
  }
  // mulberry32: короткий детерминированный генератор с равномерным распределением.
  let state = setup.randomSeed | 0;
  Math.random = () => {
    state = (state + 0x6d2b79f5) | 0;
    let mixed = Math.imul(state ^ (state >>> 15), 1 | state);
    mixed = (mixed + Math.imul(mixed ^ (mixed >>> 7), 61 | mixed)) ^ mixed;
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
  // Cloudflare Turnstile заблокирован вместе со всеми внешними хостами. Черновик
  // берёт уже загруженный window.turnstile, не подгружая скрипт; заглушка рисует
  // пустой iframe, как виджет, и сразу отдаёт токен — капча на сервере стенда
  // выключена пустым секретом.
  const turnstile = {
    render(element: HTMLElement, params: { callback?: (token: string) => void }): string {
      element.appendChild(document.createElement("iframe"));
      window.setTimeout(() => params.callback?.("parity-captcha"), 0);
      return "parity-widget";
    },
    remove(): void {},
    reset(): void {},
  };
  Object.defineProperty(window, "turnstile", { value: turnstile, configurable: true });
}

export async function installPageSetup(context: BrowserContext, setup: PageSetup): Promise<void> {
  await context.addInitScript(setUpPage, setup);
}
