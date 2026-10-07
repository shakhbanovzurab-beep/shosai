// Interactive scenarios of the RTL smoke test: each gets a fresh page whose language cookie is `language`.

import { KANBAN_SCENARIOS } from "./kanban.mjs";

/** Picking a language in the user menu re-renders the page in it, in place, without a reload. */
const switchLanguage = {
  name: "switch language from the user menu",
  language: "en",
  async run({ page, base, expect }) {
    await page.goto(new URL("/app/productivity", base).href, { waitUntil: "networkidle" });
    await page.evaluate(() => {
      window.__sameDocument = true;
    });
    await page.locator('[data-slot="sidebar-footer"] [data-sidebar="menu-button"]').click();
    await page.getByRole("menuitem", { name: "Language" }).click();
    await page.getByRole("menuitemradio", { name: "العربية" }).click();
    await page.waitForFunction(() => document.documentElement.lang === "ar", null, { timeout: 15000 });
    const state = await page.evaluate(() => ({
      dir: document.documentElement.dir,
      sameDocument: window.__sameDocument === true,
      cookie: document.cookie,
    }));
    expect(state.dir === "rtl", `switch language: dir is ${state.dir} after picking Arabic`);
    expect(state.sameDocument, "switch language: the page reloaded instead of re-rendering");
    expect(state.cookie.includes("ui_language=ar"), "switch language: the choice wasn’t remembered");
  },
};

export const SCENARIOS = [switchLanguage, ...KANBAN_SCENARIOS];
