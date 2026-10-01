// Раздача собранного фронтенда цели через перехват запросов браузера.
//
// Сервера нет: Playwright отвечает на запросы к ORIGIN файлами с диска. SPA живёт
// под /app/ (неизвестный путь под ним — index.html), шрифты под /fonts/, иконки в
// корне — как у бэкенда черновика. Всё остальное получает 404.

import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import type { Route } from "@playwright/test";

export interface SiteFiles {
  /** Каталог сборки SPA: index.html и assets/. */
  readonly appDir: string;
  /** Каталоги шрифтов; файл ищется по порядку, как у бэкенда черновика. */
  readonly fontDirs: readonly string[];
  /** Каталог корневых файлов: favicon.svg, favicon.ico, apple-touch-icon.png. */
  readonly rootDir: string;
}

const CONTENT_TYPES: Readonly<Record<string, string>> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".mp3": "audio/mpeg",
  ".webmanifest": "application/manifest+json",
};

/** Файл внутри каталога или null: путь из URL не выходит за пределы каталога. */
function fileInside(dir: string, relative: string): string | null {
  const candidate = path.resolve(dir, relative);
  if (candidate !== dir && !candidate.startsWith(dir + path.sep)) return null;
  return existsSync(candidate) && statSync(candidate).isFile() ? candidate : null;
}

async function fulfillFile(route: Route, file: string): Promise<void> {
  const contentType = CONTENT_TYPES[path.extname(file)] ?? "application/octet-stream";
  await route.fulfill({ status: 200, contentType, body: readFileSync(file) });
}

/** Отвечает на запрос к ORIGIN вне /v1. */
export async function serveSite(route: Route, url: URL, files: SiteFiles): Promise<void> {
  const pathname = decodeURIComponent(url.pathname);
  if (pathname === "/app" || pathname.startsWith("/app/")) {
    const asset = fileInside(files.appDir, pathname.slice("/app/".length));
    return fulfillFile(route, asset ?? path.join(files.appDir, "index.html"));
  }
  if (pathname.startsWith("/fonts/")) {
    const name = pathname.slice("/fonts/".length);
    for (const dir of files.fontDirs) {
      const font = fileInside(dir, name);
      if (font !== null) return fulfillFile(route, font);
    }
    return route.fulfill({ status: 404 });
  }
  const rootFile = fileInside(files.rootDir, pathname.slice(1));
  if (rootFile !== null && path.dirname(rootFile) === files.rootDir) return fulfillFile(route, rootFile);
  return route.fulfill({ status: 404 });
}
