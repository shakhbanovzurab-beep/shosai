import type { Plugin } from "vite";

import { cpSync, readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve, sep } from "node:path";

/**
 * Шрифты доски встречи (Excalidraw, meetings A11b) — с сайта кабинета, а не с CDN: так их пропускает CSP и
 * никто третий не видит, что человек открыл доску. В сборку они копируются в `wb/fonts/` (на edge —
 * `/app/wb/fonts/`, имена с хешем), в разработке отдаются прямо из пакета.
 */

export const BOARD_FONTS_URL = "/app/wb/fonts";

/** Каталог шрифтов в пакете Excalidraw. */
export function fontsDirectory(): string {
  const require = createRequire(import.meta.url);
  // Пакет не открывает свой package.json: шрифты лежат рядом с его сборкой, `dist/prod/fonts`.
  return join(dirname(require.resolve("@excalidraw/excalidraw")), "fonts");
}

/** Файл шрифта по пути запроса; null — путь выходит за каталог шрифтов или файла нет. */
export function fontFile(root: string, url: string): string | null {
  const file = resolve(root, `.${decodeURIComponent(url.split("?")[0] ?? "")}`);
  if (!file.startsWith(root + sep)) return null;
  try {
    return statSync(file).isFile() ? file : null;
  } catch {
    return null;
  }
}

export function boardFonts(): Plugin {
  const root = fontsDirectory();
  let outDir = "dist";
  return {
    name: "shosai:board-fonts",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    writeBundle() {
      cpSync(root, join(outDir, "wb", "fonts"), { recursive: true });
    },
    configureServer(server) {
      server.middlewares.use(BOARD_FONTS_URL, (request, response, next) => {
        const file = fontFile(root, request.url ?? "/");
        if (!file) return next();
        response.setHeader("content-type", "font/woff2");
        response.end(readFileSync(file));
      });
    },
  };
}
