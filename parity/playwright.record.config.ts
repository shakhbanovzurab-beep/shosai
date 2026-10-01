// Конфигурация записи фикстур (recording/record.sh). Визиты идут строго по
// одному: они делят базу стенда, а порядок запросов к ней должен повторяться.

import { defineConfig } from "@playwright/test";

import { loadParityConfig } from "./src/config.ts";
import { CHROMIUM_ARGS } from "./src/determinism/browser-flags.ts";

const config = loadParityConfig();

export default defineConfig({
  testDir: "src/recording",
  testMatch: "record.spec.ts",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  outputDir: ".cache/record-results",
  use: {
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "ru-RU",
    timezoneId: config.timezone,
    colorScheme: "light",
    serviceWorkers: "block",
    launchOptions: { args: [...CHROMIUM_ARGS] },
  },
});
