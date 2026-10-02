import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config.ts";

// Тесты живут в tests/ и собираются тем же конфигом Vite, что и приложение:
// те же алиасы и плагины, поэтому тест видит модуль ровно таким, каким его
// увидит сборка.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      include: ["tests/**/*.test.{ts,tsx}"],
      environment: "jsdom",
      restoreMocks: true,
      unstubGlobals: true,
    },
  }),
);
