import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import { bootScripts } from "./tooling/boot-script";
import { cabinetPaths } from "./tooling/cabinet-paths";
import { i18nCatalogues } from "./tooling/i18n-catalogues";
import { mermaidWithoutElk } from "./tooling/mermaid-without-elk";
import { messageTypes } from "./tooling/message-types";
import { mockWorker } from "./tooling/mock-worker";
import { fileURLToPath } from "node:url";

const path = (relative: string) => fileURLToPath(new URL(relative, import.meta.url));

// Кабинет — статическое SPA под /app/ (ADR 0021). Режим `api` (npm run dev:api) ходит в локальный
// бэкенд вместо моков; адрес бэкенда — переменная окружения BACKEND_URL (по умолчанию localhost:8000).
export default defineConfig(({ mode }) => ({
  base: "/app/",
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
    messageTypes(path("./src/i18n/messages/en")),
    i18nCatalogues(path("./src/i18n/messages")),
    bootScripts(),
    mockWorker(),
    cabinetPaths(),
    mermaidWithoutElk(),
  ],
  resolve: { alias: { "@": path("./src") } },
  server: {
    port: 3000,
    proxy:
      mode === "api"
        ? {
            "/v1": process.env.BACKEND_URL ?? "http://localhost:8000",
            // Скачивания как через edge (FL-D9): /dl/{дом}/… уходит в бакет тем же запросом.
            "^/dl/(ru|eu)/": {
              target: process.env.BUCKET_URL ?? "http://127.0.0.1:18333",
              changeOrigin: true,
              rewrite: (url) => url.replace(/^\/dl\/(ru|eu)/, ""),
            },
          }
        : undefined,
  },
  preview: { port: 3000 },
  build: {
    target: "es2023",
    sourcemap: false,
    rolldownOptions: {
      output: {
        minify: { compress: { dropConsole: true } },
        // Иконки lucide, общие для многих страниц, — одним чанком, а не сотней запросов по 200 байт
        // (замер на /app/productivity: 147 файлов JS → 92, gzip 463 → 467 КБ).
        codeSplitting: { groups: [{ name: "icons", test: /node_modules[\\/]lucide-react[\\/]/ }] },
      },
    },
  },
  test: {
    include: ["src/**/*.test.ts", "tooling/**/*.test.ts"],
    environment: "node",
    testTimeout: 60_000,
  },
}));
