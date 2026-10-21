// Замер доски Канбана на демо-данных (план пакета Kanban golden core, §5.4): INP перетаскивания карточки мышью и
// клавиатурой на доске из 300 карточек и CLS, пока карточки грузятся и двигаются. Цели: INP < 200 мс, CLS ≤ 0,1.
// Нужен запущенный кабинет на моках: npm run perf:kanban -- --base http://localhost:3417 [--board load-300] [--cpu 4]

import { chromium } from "playwright-core";

import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: { base: { type: "string" }, board: { type: "string" }, cpu: { type: "string" } },
});
const BASE = new URL(values.base ?? "http://localhost:3000");
const BOARD = values.board ?? "load-300";
const CPU = Number(values.cpu ?? "1");

// Собирает задержки взаимодействий (Event Timing) и сдвиги без недавнего ввода (layout-shift) с первой отрисовки.
const OBSERVE = () => {
  const vitals = { events: [], shift: 0 };
  globalThis.__kanbanVitals = vitals;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries())
      if (entry.interactionId) vitals.events.push({ name: entry.name, duration: entry.duration });
  }).observe({ type: "event", durationThreshold: 16, buffered: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) if (!entry.hadRecentInput) vitals.shift += entry.value;
  }).observe({ type: "layout-shift", buffered: true });
};

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "en-US" });
await context.addCookies([{ name: "ui_language", value: "en", url: BASE.origin }]);
await context.addInitScript(() => sessionStorage.setItem("kanban-demo-large", "1"));
await context.addInitScript(OBSERVE);
const page = await context.newPage();
if (CPU > 1) await (await context.newCDPSession(page)).send("Emulation.setCPUThrottlingRate", { rate: CPU });

await page.goto(new URL(`/app/kanban?board=${BOARD}`, BASE).href, { waitUntil: "networkidle", timeout: 180000 });
const cards = page.locator("[data-task-id]");
await cards.first().waitFor({ timeout: 180000 });
const rendered = await cards.count();
await page.waitForTimeout(1000);
const loadShift = await page.evaluate(() => globalThis.__kanbanVitals.shift);

// Мышью: из первой колонки в третью, шагами, как живая рука.
const from = await cards.first().boundingBox();
const target = await page.locator("section[data-column-id]").nth(2).boundingBox();
await page.mouse.move(from.x + from.width / 2, from.y + 20);
await page.mouse.down();
for (let step = 1; step <= 20; step++)
  await page.mouse.move(
    from.x + from.width / 2 + ((target.x + 40 - from.x) * step) / 20,
    from.y + 20 + ((target.y + 160 - from.y) * step) / 20,
  );
await page.mouse.up();
await page.waitForTimeout(800);

// Клавиатурой: пробел поднимает, стрелка вправо переносит в соседнюю колонку, пробел кладёт.
await cards.nth(5).focus();
for (const key of ["Space", "ArrowRight", "ArrowDown", "Space"]) {
  await page.keyboard.press(key);
  await page.waitForTimeout(300);
}
await page.waitForTimeout(800);

const vitals = await page.evaluate(() => globalThis.__kanbanVitals);
const inp = Math.max(0, ...vitals.events.map((e) => e.duration));
const result = {
  board: BOARD,
  cpuSlowdown: CPU,
  cardsRendered: rendered,
  interactions: vitals.events.length,
  inpMs: Math.round(inp),
  clsOnLoad: Number(loadShift.toFixed(4)),
  clsTotal: Number(vitals.shift.toFixed(4)),
  pass: inp < 200 && vitals.shift <= 0.1,
  slowest: vitals.events.toSorted((a, b) => b.duration - a.duration).slice(0, 4),
};
console.log(JSON.stringify(result));
await browser.close();
process.exit(result.pass ? 0 : 1);
