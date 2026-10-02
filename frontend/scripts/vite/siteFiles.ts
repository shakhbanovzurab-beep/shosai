// Корневые файлы сайта и шрифты — мимо сборщика, по адресам черновика.
//
// Кабинет живёт под /app/, а иконки, манифест установки и шрифты — в корне
// сайта: /favicon.svg, /manifest.webmanifest, /fonts/roles-ru-whisperer.css.
// Их адреса знают лендинг, установленное приложение и закладки, поэтому Vite
// не должен ни переименовывать их хешем, ни переносить под /app/ (что делает
// его publicDir). Плагин раздаёт их в разработке и превью, а в сборке копирует:
// public/* → dist/*, fonts/*.{woff2,css} → dist/fonts/ (ADR 0018).

import { copyFileSync, createReadStream, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { extname, join, resolve } from "node:path";

import type { Plugin } from "vite";

export interface SiteFilesOptions {
  /** Каталог корневых файлов сайта (иконки, манифест установки). */
  readonly rootFilesDir: string;
  /** Каталог шрифтов: woff2 и таблицы стилей `roles-<lang>-<role>.css`. */
  readonly fontsDir: string;
}

const CONTENT_TYPES: Readonly<Record<string, string>> = {
  ".woff2": "font/woff2",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".webmanifest": "application/manifest+json",
};

/** Шрифтовой каталог раздаёт только шрифты и их таблицы, но не манифест faces.json. */
const FONT_EXTENSIONS: ReadonlySet<string> = new Set([".woff2", ".css"]);

/** Каталоги плоские: имя без разделителей и `..` не выходит за их пределы. */
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

function fileIn(dir: string, name: string, extensions?: ReadonlySet<string>): string | null {
  if (!SAFE_NAME.test(name) || !Object.hasOwn(CONTENT_TYPES, extname(name))) return null;
  if (extensions !== undefined && !extensions.has(extname(name))) return null;
  const file = join(dir, name);
  return existsSync(file) && statSync(file).isFile() ? file : null;
}

type Middleware = (request: IncomingMessage, response: ServerResponse, next: () => void) => void;

/** Путь запроса без процентного кодирования; битое кодирование — не наш файл. */
function decodedPath(url: string | undefined): string | null {
  try {
    return decodeURIComponent(new URL(url ?? "/", "http://site").pathname);
  } catch {
    return null;
  }
}

function serveFrom(rootFilesDir: string, fontsDir: string): Middleware {
  return (request, response, next) => {
    const pathname = decodedPath(request.url);
    if (pathname === null) {
      next();
      return;
    }
    const file = pathname.startsWith("/fonts/")
      ? fileIn(fontsDir, pathname.slice("/fonts/".length), FONT_EXTENSIONS)
      : fileIn(rootFilesDir, pathname.slice(1));
    if (file === null) {
      next();
      return;
    }
    response.setHeader("Content-Type", CONTENT_TYPES[extname(file)] ?? "application/octet-stream");
    createReadStream(file).pipe(response);
  };
}

function copyFlat(from: string, to: string, extensions?: ReadonlySet<string>): void {
  mkdirSync(to, { recursive: true });
  for (const name of readdirSync(from)) {
    if (fileIn(from, name, extensions) !== null) copyFileSync(join(from, name), join(to, name));
  }
}

export function siteFiles({ rootFilesDir, fontsDir }: SiteFilesOptions): Plugin {
  let outDir = "";
  return {
    name: "whisperer-site-files",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    // Подключается до встроенных обработчиков Vite: адреса вне базы /app/ они не отдают.
    configureServer(server) {
      server.middlewares.use(serveFrom(rootFilesDir, fontsDir));
    },
    // Превью раздаёт уже собранное — ровно то, что уедет в прод.
    configurePreviewServer(server) {
      server.middlewares.use(serveFrom(outDir, join(outDir, "fonts")));
    },
    writeBundle() {
      copyFlat(rootFilesDir, outDir);
      copyFlat(fontsDir, join(outDir, "fonts"), FONT_EXTENSIONS);
    },
  };
}
