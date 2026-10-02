import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PassThrough } from "node:stream";

import type { Connect, PreviewServer, ResolvedConfig, ViteDevServer } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { siteFiles } from "../../scripts/vite/siteFiles.ts";

type Middleware = Connect.NextHandleFunction;
type Outcome = { readonly served: false } | { readonly served: true; readonly type: string; readonly body: string };

const workspace = mkdtempSync(join(tmpdir(), "whisperer-site-files-"));
const rootFilesDir = join(workspace, "public");
const fontsDir = join(workspace, "fonts");
const plugin = siteFiles({ rootFilesDir, fontsDir });

/** Хуки плагина объявлены функциями; тест вызывает их напрямую. */
const hook = <T>(value: unknown): T => {
  if (typeof value !== "function") throw new Error("Хук плагина не функция");
  return value as T;
};

function middlewareOf(register: (server: ViteDevServer & PreviewServer) => void): Middleware {
  let captured: Middleware | null = null;
  register({ middlewares: { use: (fn: Middleware) => (captured = fn) } } as unknown as ViteDevServer & PreviewServer);
  if (captured === null) throw new Error("Плагин не подключил обработчик");
  return captured;
}

function request(middleware: Middleware, url: string): Promise<Outcome> {
  return new Promise((resolve) => {
    const response = Object.assign(new PassThrough(), {
      headers: new Map<string, string>(),
      setHeader(name: string, value: string) {
        response.headers.set(name, value);
      },
    });
    const chunks: Buffer[] = [];
    response.on("data", (chunk: Buffer) => chunks.push(chunk));
    response.on("end", () =>
      resolve({ served: true, type: response.headers.get("Content-Type") ?? "", body: Buffer.concat(chunks).toString() }),
    );
    middleware({ url } as IncomingMessage, response as unknown as ServerResponse, () => resolve({ served: false }));
  });
}

describe("корневые файлы сайта и шрифты", () => {
  beforeAll(() => {
    mkdirSync(rootFilesDir);
    mkdirSync(fontsDir);
    writeFileSync(join(rootFilesDir, "favicon.svg"), "<svg/>");
    writeFileSync(join(rootFilesDir, "manifest.webmanifest"), "{}");
    writeFileSync(join(fontsDir, "roles-ru-whisperer.css"), "@font-face{}");
    writeFileSync(join(fontsDir, "onest-latin.woff2"), "woff2");
    writeFileSync(join(fontsDir, "faces.json"), "[]");
    writeFileSync(join(workspace, "secret.txt"), "секрет");
    hook<(config: ResolvedConfig) => void>(plugin.configResolved)({
      root: workspace,
      build: { outDir: "dist" },
    } as ResolvedConfig);
  });

  afterAll(() => {
    rmSync(workspace, { recursive: true, force: true });
  });

  it("в разработке отдаёт шрифты под /fonts/ и корневые файлы в корне", async () => {
    const serve = middlewareOf(hook(plugin.configureServer));
    expect(await request(serve, "/fonts/roles-ru-whisperer.css")).toEqual({
      served: true,
      type: "text/css; charset=utf-8",
      body: "@font-face{}",
    });
    expect(await request(serve, "/fonts/onest-latin.woff2?v=1")).toMatchObject({ served: true, type: "font/woff2" });
    expect(await request(serve, "/favicon.svg")).toMatchObject({ served: true, type: "image/svg+xml" });
    expect(await request(serve, "/manifest.webmanifest")).toMatchObject({ type: "application/manifest+json" });
  });

  it.each([
    "/fonts/faces.json",
    "/fonts/../secret.txt",
    "/fonts/%2e%2e%2fsecret.txt",
    "/%2e%2e/secret.txt",
    "/fonts/favicon.svg",
    "/roles-ru-whisperer.css",
    "/app/favicon.svg",
    "/fonts/%E0%A4%A",
    "/.hidden.svg",
  ])("не отдаёт %s — дальше решают обработчики Vite", async (url) => {
    expect(await request(middlewareOf(hook(plugin.configureServer)), url)).toEqual({ served: false });
  });

  it("при сборке копирует корневые файлы в dist/, а шрифты без манифеста — в dist/fonts/", () => {
    hook<() => void>(plugin.writeBundle)();
    const dist = join(workspace, "dist");
    expect(readdirSync(dist).toSorted()).toEqual(["favicon.svg", "fonts", "manifest.webmanifest"]);
    expect(readdirSync(join(dist, "fonts")).toSorted()).toEqual(["onest-latin.woff2", "roles-ru-whisperer.css"]);
    expect(existsSync(join(dist, "fonts", "faces.json"))).toBe(false);
  });

  it("превью отдаёт уже собранные файлы", async () => {
    const serve = middlewareOf(hook(plugin.configurePreviewServer));
    expect(await request(serve, "/fonts/onest-latin.woff2")).toMatchObject({ served: true, body: "woff2" });
    expect(await request(serve, "/favicon.svg")).toMatchObject({ served: true, body: "<svg/>" });
  });
});
