// RTL smoke test: opens the key screens in Arabic in a real browser and checks they are written right to
// left, don't scroll sideways and keep the admin panel Russian; switches the language from the user menu.
// Needs a running server: npm run i18n:rtl-smoke -- --base http://localhost:3107 --out /tmp/rtl-shots

import { chromium } from "playwright-core";

import { SCENARIOS } from "./rtl-smoke/scenarios.mjs";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";

const { values } = parseArgs({ options: { base: { type: "string" }, out: { type: "string" } } });
const BASE = new URL(values.base ?? "http://localhost:3000");
const OUT = values.out ?? null;
if (OUT) mkdirSync(OUT, { recursive: true });

/** Screens checked in Arabic; the list grows with each localization phase. */
const SCREENS = [
  "/app/productivity",
  "/app/kanban",
  "/app/notes",
  "/app/file-manager",
  "/app/knowledge-base",
  "/app/studio",
  "/app/calendar",
  "/app/hub",
  "/app/inbox",
  "/app/w/lumen",
  "/app/w/lumen/settings",
];
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];

const failures = [];
let checks = 0;
const expect = (ok, what) => {
  checks += 1;
  if (!ok) failures.push(what);
};

const browser = await chromium.launch();
const newPage = async (language, viewport) => {
  const context = await browser.newContext({ viewport, locale: "en-US" });
  await context.addCookies([{ name: "ui_language", value: language, url: BASE.origin }]);
  return context.newPage();
};
const documentState = (page) =>
  page.evaluate(() => {
    const sidebar = document.querySelector('[data-slot="sidebar-container"]')?.getBoundingClientRect();
    const inset = document.querySelector('[data-slot="sidebar-inset"]')?.getBoundingClientRect();
    const leo = document.querySelector('[aria-controls="leo-panel"]')?.getBoundingClientRect();
    return {
      lang: document.documentElement.lang,
      dir: document.documentElement.dir,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      // Where the desktop sidebar and the page sit; null on mobile, where the sidebar is a sheet.
      layout:
        sidebar && inset && sidebar.width > 0
          ? {
              sidebarLeft: sidebar.left,
              sidebarRight: sidebar.right,
              insetLeft: inset.left,
              insetRight: inset.right,
              leo: leo ? { left: leo.left, right: leo.right } : null,
            }
          : null,
    };
  });

/** The sidebar is on the reading side and the page beside it, never under it. */
const checkLayout = (state, where) => {
  if (!state.layout) return;
  const { sidebarLeft, sidebarRight, insetLeft, insetRight, leo } = state.layout;
  if (leo) expect(leo.right <= sidebarLeft || leo.left >= sidebarRight, `${where}: the Leo button covers the sidebar`);
  if (state.dir === "rtl") {
    expect(sidebarLeft > insetLeft, `${where}: the sidebar isn’t on the right`);
    expect(insetRight <= sidebarLeft + 1, `${where}: the page runs under the sidebar`);
  } else {
    expect(sidebarRight < insetRight, `${where}: the sidebar isn’t on the left`);
    expect(insetLeft >= sidebarRight - 1, `${where}: the page runs under the sidebar`);
  }
};

try {
  for (const viewport of VIEWPORTS) {
    const page = await newPage("ar", viewport);
    for (const path of SCREENS) {
      await page.goto(new URL(path, BASE).href, { waitUntil: "networkidle" });
      const state = await documentState(page);
      const where = `${path} (${viewport.name})`;
      expect(state.lang === "ar" && state.dir === "rtl", `${where}: <html lang dir> is ${state.lang}/${state.dir}`);
      expect(state.overflow <= 1, `${where}: scrolls sideways by ${state.overflow}px`);
      checkLayout(state, where);
      if (OUT) await page.screenshot({ path: join(OUT, `ar-${viewport.name}${path.replaceAll("/", "-")}.png`) });
    }
    await page.context().close();
  }

  // The admin panel is Russian and left to right whatever the user picked for /app.
  const admin = await newPage("ar", VIEWPORTS[0]);
  await admin.goto(new URL("/admin/dashboard", BASE).href, { waitUntil: "networkidle" });
  const adminState = await documentState(admin);
  expect(
    adminState.lang === "ru" && adminState.dir === "ltr",
    `/admin: <html lang dir> is ${adminState.lang}/${adminState.dir}`,
  );
  checkLayout(adminState, "/admin");
  await admin.context().close();

  for (const scenario of SCENARIOS) {
    const page = await newPage(scenario.language, VIEWPORTS[0]);
    try {
      await scenario.run({ page, base: BASE, expect, out: OUT });
    } catch (error) {
      failures.push(`${scenario.name}: ${error instanceof Error ? error.message.split("\n")[0] : error}`);
    }
    await page.context().close();
  }
} finally {
  await browser.close();
}

for (const failure of failures) console.error(failure);
console.log(`RTL smoke: ${failures.length === 0 ? "passed" : `${failures.length} failure(s)`}, ${checks} checks.`);
process.exitCode = failures.length === 0 ? 0 : 1;
