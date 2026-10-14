import { loadTurnstile, type ScriptHost, type TurnstileApi, type TurnstileOptions } from "../api/turnstile-script";

/** Ключ сайта Turnstile из сборки (F4); пусто — проверка недоступна, и форма об этом говорит. */
export function turnstileSiteKey(): string | null {
  const key = import.meta.env.VITE_TURNSTILE_SITE_KEY?.trim();
  return key ? key : null;
}

/** Настоящая страница: скрипт в <head>, таймер браузера. */
export const browserHost: ScriptHost = {
  turnstile: () => (window as Window & { turnstile?: TurnstileApi }).turnstile,
  appendScript(src, onLoad, onError) {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener("error", onError, { once: true });
    document.head.append(script);
  },
  after(milliseconds, run) {
    const timer = window.setTimeout(run, milliseconds);
    return () => window.clearTimeout(timer);
  },
};

// Turnstile называет языки по-своему: китайский традиционный — zh-tw, бразильский португальский — pt-br.
const TURNSTILE_LANGUAGES: Readonly<Record<string, string>> = { "zh-Hant": "zh-tw", "pt-BR": "pt-br" };

/** Язык виджета для языка интерфейса. */
export function turnstileLanguage(locale: string): string {
  return TURNSTILE_LANGUAGES[locale] ?? locale;
}

/** Поставить проверку в элемент; промис отдаёт уборку виджета, отказ — проверка не загрузилась. */
export async function mountTurnstile(element: HTMLElement, options: TurnstileOptions): Promise<() => void> {
  const api = await loadTurnstile(browserHost);
  const widget = api.render(element, options);
  return () => api.remove(widget);
}
