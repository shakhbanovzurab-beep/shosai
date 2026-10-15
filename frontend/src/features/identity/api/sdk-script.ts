// Скрипты фирменных виджетов входа (Яндекс ID, Google): грузятся модулем, а не inline-тегом, — так их разрешает
// CSP; один раз на страницу. Загрузка всегда заканчивается: успехом, ошибкой или таймаутом, и кнопка сервиса
// тогда заменяется обычной ссылкой входа.

export const SDK_TIMEOUT_MS = 9000;

const loading = new Map<string, Promise<void>>();

/** Поставить скрипт на страницу; общей бывает только идущая загрузка, после провала скрипт грузится заново. */
export function loadSdk(src: string, timeoutMs = SDK_TIMEOUT_MS): Promise<void> {
  const present = document.querySelector(`script[src="${CSS.escape(src)}"][data-loaded]`);
  if (present) return Promise.resolve();
  const running = loading.get(src);
  if (running !== undefined) return running;
  const started = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    const timer = window.setTimeout(() => reject(new Error(`sdk timeout: ${src}`)), timeoutMs);
    script.src = src;
    script.async = true;
    script.addEventListener(
      "load",
      () => {
        window.clearTimeout(timer);
        script.dataset.loaded = "true";
        resolve();
      },
      { once: true },
    );
    script.addEventListener(
      "error",
      () => {
        window.clearTimeout(timer);
        script.remove();
        reject(new Error(`sdk failed: ${src}`));
      },
      { once: true },
    );
    document.head.append(script);
  }).finally(() => loading.delete(src));
  loading.set(src, started);
  return started;
}
