// Подготовка страницы до первого скрипта приложения: localStorage, генератор
// случайных чисел с фиксированным зерном, заглушки капчи и распознавания речи,
// а при съёмке ещё и остановленные анимации и учёт изменений DOM.
//
// Функция `setUpPage` выполняется в браузере и сериализуется Playwright, поэтому
// она самодостаточна: никаких замыканий и импортов.

import type { BrowserContext } from "@playwright/test";

/** Зерно Math.random — одно для записи и съёмки: случайный выбор совпадает. */
export const RANDOM_SEED = 0x2f6b1d;

export interface PageSetup {
  /** Ключи localStorage: сессия (wh-auth), тема (wh.theme), язык (wh.lang). */
  readonly storage: Readonly<Record<string, string>>;
  /** Ключи sessionStorage: заявка зрителя на вход в эфир (wh.stream.knock.<приглашение>). */
  readonly session?: Readonly<Record<string, string>>;
  readonly randomSeed: number;
  /**
   * Съёмка: анимации и переходы нулевой длины с первого кадра и счётчик
   * изменений DOM. Пилот показал, что анимация появления (`.rise`) оставляет
   * текст на дробном смещении, и снимок получался одним из двух разных.
   */
  readonly freezeMotion: boolean;
  /** Селекторы анимаций, которые при съёмке стоят на первом кадре (PERSISTENT_ANIMATIONS). */
  readonly persistentAnimations: readonly string[];
}

/**
 * Анимации, по концу которых интерфейс меняется. Черновик закрывает тост, когда
 * кончается анимация его полоски `toast-bar` (shared/ui/Toaster.tsx). Если v2
 * устроит закрытие тоста иначе, F2 дописывает сюда свой селектор.
 */
export const PERSISTENT_ANIMATIONS: readonly string[] = ['[style*="toast-bar"]'];

function setUpPage(setup: PageSetup): void {
  for (const [key, value] of Object.entries(setup.storage)) {
    window.localStorage.setItem(key, value);
  }
  for (const [key, value] of Object.entries(setup.session ?? {})) {
    window.sessionStorage.setItem(key, value);
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
  // пустой iframe размером настоящего виджета (300×65, без рамки) и сразу
  // отдаёт токен.
  const turnstile = {
    render(element: HTMLElement, params: { callback?: (token: string) => void }): string {
      const frame = document.createElement("iframe");
      frame.style.cssText = "width:300px;height:65px;border:0;display:block";
      element.appendChild(frame);
      window.setTimeout(() => params.callback?.("parity-captcha"), 0);
      return "parity-widget";
    },
    remove(): void {},
    reset(): void {},
  };
  Object.defineProperty(window, "turnstile", { value: turnstile, configurable: true });
  // Распознавание речи Chromium шлёт звук на серверы Google из процесса браузера,
  // мимо перехвата страницы. Заглушка запускается и молчит: экран тот же, что у
  // пользователя Chrome, пока он ничего не сказал, а в сеть ничего не уходит.
  class SilentRecognition extends EventTarget {
    continuous = false;
    interimResults = false;
    lang = "";
    onstart: ((event: Event) => void) | null = null;
    onend: ((event: Event) => void) | null = null;
    onresult: ((event: Event) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    start(): void {
      window.setTimeout(() => {
        const event = new Event("start");
        this.dispatchEvent(event);
        this.onstart?.(event);
      }, 0);
    }
    stop(): void {
      const event = new Event("end");
      this.dispatchEvent(event);
      this.onend?.(event);
    }
    abort(): void {
      this.stop();
    }
  }
  for (const name of ["SpeechRecognition", "webkitSpeechRecognition"]) {
    Object.defineProperty(window, name, { value: SilentRecognition, configurable: true });
  }
  if (!setup.freezeMotion) return;

  // Анимации, конец которых меняет экран (полоска тоста закрывает тост по
  // animationend), не обнуляются, а стоят на первом кадре: иначе тост исчез бы
  // через доли секунды. Селектор специфичнее `*`, поэтому перекрывает общее правило.
  const persistent = setup.persistentAnimations.join(",");
  const motion =
    "*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;" +
    "transition-duration:0s!important;transition-delay:0s!important;caret-color:transparent!important}" +
    (persistent === ""
      ? ""
      : `${persistent}{animation-duration:100000s!important;animation-delay:0s!important;animation-play-state:paused!important}`);
  const tracker = window as unknown as { __parityLastMutation: number };
  tracker.__parityLastMutation = performance.now();
  const install = (): void => {
    const style = document.createElement("style");
    style.textContent = motion;
    document.documentElement.appendChild(style);
    new MutationObserver(() => {
      tracker.__parityLastMutation = performance.now();
    }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
  };
  if (document.documentElement !== null) install();
  else {
    new MutationObserver((_records, observer) => {
      if (document.documentElement === null) return;
      observer.disconnect();
      install();
    }).observe(document, { childList: true });
  }
}

export async function installPageSetup(context: BrowserContext, setup: PageSetup): Promise<void> {
  await context.addInitScript(setUpPage, setup);
}
