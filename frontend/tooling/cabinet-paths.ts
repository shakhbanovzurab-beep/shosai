import type { Connect, Plugin } from "vite";

/**
 * Пути кабинета вне `base` (/app/): граница отдаёт на них index.html кабинета (ADR 0021 §3, F2-D5).
 * Тот же список нужен F4 для правил NGINX.
 */
export const CABINET_TOP_LEVEL_PATHS = ["/app", "/admin", "/oauth/callback", "/unauthorized"] as const;

/** Страницы, которые есть только с моками в `npm run dev` (src/mocks). */
const DEV_ONLY_PATHS = ["/oauth/demo-authorize"] as const;

const matches = (paths: readonly string[], pathname: string) =>
  paths.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));

// Отдаёт index.html кабинета на его пути вне /app/, как это делает граница в продакшене.
const fallback =
  (base: string, paths: readonly string[]): Connect.NextHandleFunction =>
  (request, _response, next) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    const page = url.pathname === "/app" || !url.pathname.startsWith(base);
    if (request.method === "GET" && page && matches(paths, url.pathname)) request.url = `${base}index.html`;
    next();
  };

/** Fallback путей кабинета для `vite` и `vite preview`. */
export function cabinetPaths(): Plugin {
  let base = "/";
  return {
    name: "whisperer:cabinet-paths",
    configResolved(config) {
      base = config.base;
    },
    configureServer(server) {
      server.middlewares.use(fallback(base, [...CABINET_TOP_LEVEL_PATHS, ...DEV_ONLY_PATHS]));
    },
    configurePreviewServer(server) {
      server.middlewares.use(fallback(base, CABINET_TOP_LEVEL_PATHS));
    },
  };
}
