import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  // Кабинет живёт под /app/, как в черновике: те же адреса, что знают
  // пользователи, закладки и нативные клиенты. Ассеты → /app/assets/*.
  base: "/app/",
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Синтаксис понижается до ES2020, как в черновике: кто открывает кабинет
    // сегодня, должен открыть его и после переписывания.
    target: "es2020",
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
