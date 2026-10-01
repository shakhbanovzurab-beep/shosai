// Конфигурация съёмки (src/parity.spec.ts): один проект Playwright на ячейку
// матрицы. Тест помечен тегами своих ячеек, проект берёт тесты по своему тегу.
// Эталон лежит в .cache/baseline/<ячейка>/<состояние>.png — локальная копия
// снимков из S3 (scripts/parity.sh), в git только манифест хешей.

import { defineConfig } from "@playwright/test";

import { loadParityConfig } from "./src/config.ts";
import { cellGrep } from "./src/cell-grep.ts";
import { allCells, browserLocale, VIEWPORTS, type Cell } from "./src/matrix.ts";

const config = loadParityConfig();

export default defineConfig<{ cell: Cell }>({
  testDir: "src",
  testMatch: "parity.spec.ts",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: Number(process.env["PARITY_WORKERS"] ?? 4),
  retries: 0,
  // JSON-отчёт читает src/cli/parity.ts: по нему видно, какие снимки сняты.
  reporter: [
    ["list"],
    ["json", { outputFile: ".cache/results.json" }],
    ["html", { outputFolder: ".cache/report", open: "never" }],
  ],
  outputDir: ".cache/results",
  snapshotDir: ".cache/baseline",
  snapshotPathTemplate: "{snapshotDir}/{projectName}/{arg}{ext}",
  use: {
    timezoneId: config.timezone,
    serviceWorkers: "block",
    deviceScaleFactor: 1,
    // «Уменьшить движение»: черновик останавливает по нему постер входа, взгляд
    // Leo и игру экрана разрыва связи — то, что иначе меняет кадр каждые
    // миллисекунды. v2 обязан уважать эту настройку так же.
    reducedMotion: "reduce",
  },
  projects: allCells().map((cell) => {
    const viewport = VIEWPORTS[cell.viewport];
    return {
      name: cell.name,
      grep: cellGrep(cell.name),
      use: {
        cell,
        viewport: { width: viewport.width, height: viewport.height },
        hasTouch: viewport.touch,
        locale: browserLocale(cell.language),
        colorScheme: cell.theme,
      },
    };
  }),
});
