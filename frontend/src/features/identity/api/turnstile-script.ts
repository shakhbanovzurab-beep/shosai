// Cloudflare Turnstile (ID-D1): проверка, что входит человек. Скрипт грузится модулем, а не inline-тегом, —
// так его разрешает CSP; один раз на страницу. Загрузка всегда заканчивается: успехом, ошибкой или таймаутом,
// и форма объясняет, почему она ждёт.

export const TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
export const LOAD_TIMEOUT_MS = 9000;

export interface TurnstileOptions {
  sitekey: string;
  callback: (token: string) => void;
  "error-callback": () => void;
  "expired-callback": () => void;
  theme: "auto";
  language: string;
}

export interface TurnstileApi {
  render(container: HTMLElement, options: TurnstileOptions): string;
  remove(widgetId: string): void;
}

/** Страница, на которую ставится скрипт; в тестах — подделка. */
export interface ScriptHost {
  turnstile(): TurnstileApi | undefined;
  appendScript(src: string, onLoad: () => void, onError: () => void): void;
  after(milliseconds: number, run: () => void): () => void;
}

let loading: Promise<TurnstileApi> | null = null;

/** API Turnstile. Общей бывает только идущая загрузка: после неё API берётся со страницы, после провала — грузится заново. */
export function loadTurnstile(host: ScriptHost, timeoutMs = LOAD_TIMEOUT_MS): Promise<TurnstileApi> {
  const ready = host.turnstile();
  if (ready) return Promise.resolve(ready);
  loading ??= new Promise<TurnstileApi>((resolve, reject) => {
    const cancel = host.after(timeoutMs, () => reject(new Error("turnstile_timeout")));
    host.appendScript(
      TURNSTILE_URL,
      () => {
        cancel();
        const api = host.turnstile();
        if (api) resolve(api);
        else reject(new Error("turnstile_missing"));
      },
      () => {
        cancel();
        reject(new Error("turnstile_failed"));
      },
    );
  }).finally(() => {
    loading = null;
  });
  return loading;
}
