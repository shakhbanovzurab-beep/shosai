import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

import { siteFiles } from "./scripts/vite/siteFiles.ts";

const fromRoot = (path: string): string => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  // Кабинет живёт под /app/, как в черновике: те же адреса, что знают
  // пользователи, закладки и нативные клиенты. Ассеты → /app/assets/*.
  base: "/app/",
  // Корневые файлы сайта раздаёт и копирует siteFiles: publicDir Vite перенёс
  // бы их адреса под /app/.
  publicDir: false,
  // Tailwind v4 настраивается из CSS (src/core/styles/main.css), JS-конфига нет.
  plugins: [
    react(),
    tailwindcss(),
    siteFiles({ rootFilesDir: fromRoot("./public"), fontsDir: fromRoot("./fonts") }),
  ],
  resolve: {
    alias: { "@": fromRoot("./src") },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Синтаксис понижается до ES2020, как в черновике: кто открывает кабинет
    // сегодня, должен открыть его и после переписывания.
    target: "es2020",
    // Цель CSS — базовая линия браузеров Tailwind v4: старше неё стили кабинета
    // не работают всё равно (слои каскада, @property). С целью es2020 минификатор
    // понижал логические свойства и оставлял пустым @keyframes conn-packet.
    cssTarget: ["chrome111", "edge111", "firefox128", "safari16.4"],
    // Шрифт никогда не вшивается в CSS: подмножества по unicode-range для того
    // и разложены, чтобы качать только нужное.
    assetsInlineLimit: (file) => (/\.woff2?$/.test(file) ? false : undefined),
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
