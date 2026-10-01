// Юнит-тесты стенда сравнения: без браузера, на хосте и в CI (`npm test`).

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "src",
  testMatch: "**/*.test.ts",
  fullyParallel: true,
  reporter: [["list"]],
  outputDir: ".cache/unit-results",
});
