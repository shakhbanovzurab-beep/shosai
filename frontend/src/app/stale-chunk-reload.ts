const RELOAD_KEY = "cabinet:stale-chunk-reload";
const RELOAD_INTERVAL_MS = 10_000;

/**
 * После релиза файлов прошлой сборки нет, и страница, грузящая чанк старой сборки, падает. Перезагрузка
 * получает новую сборку, но не чаще раза в 10 с, чтобы настоящий сбой не зациклился.
 */
export function reloadOnStaleChunk(): void {
  window.addEventListener("vite:preloadError", (event) => {
    let last = 0;
    try {
      last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0);
      if (Date.now() - last < RELOAD_INTERVAL_MS) return;
      sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
    } catch {
      // Хранилище недоступно (приватный режим): перезагрузка всё равно лучше упавшей страницы.
    }
    event.preventDefault();
    window.location.reload();
  });
}
