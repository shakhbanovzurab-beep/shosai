import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LOCALES } from "@/core/i18n/locales";
import { DEFAULT_FONT_ROLE, FONT_ROLES } from "@/core/theme/fontCatalogue";

const INDEX_HTML = readFileSync(join(import.meta.dirname, "../../index.html"), "utf8");
const INLINE_SCRIPTS = [...INDEX_HTML.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1] ?? "");
const PRE_PAINT = INLINE_SCRIPTS[0] ?? "";

/** Выполняет скрипт так, как его выполнит браузер при разборе index.html. */
const runPrePaint = (): void => {
  new Function(PRE_PAINT)();
};

const stubSystemDark = (dark: boolean): void => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: dark && query.includes("dark") }));
};

const appendedStylesheets = (): string[] =>
  [...document.head.querySelectorAll('link[rel="stylesheet"]')].map((link) => link.getAttribute("href") ?? "");

describe("скрипт до первого кадра", () => {
  beforeEach(() => {
    localStorage.clear();
    document.head.replaceChildren();
    const root = document.documentElement;
    root.setAttribute("lang", "ru");
    root.setAttribute("data-theme", "light");
    root.removeAttribute("data-font");
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("единственный встроенный скрипт страницы", () => {
    expect(INLINE_SCRIPTS).toHaveLength(1);
    expect(INDEX_HTML).toContain('<script type="module" src="/src/entrypoints/main.tsx"></script>');
  });

  it("знает те же роли, что каталог шрифтов, кроме фирменной", () => {
    const roles = FONT_ROLES.filter((role) => role !== DEFAULT_FONT_ROLE).map((role) => `"${role}"`);
    expect(PRE_PAINT).toContain(`[${roles.join(", ")}]`);
  });

  it("знает те же коды языков с отдельным hreflang, что реестр локалей", () => {
    const pairs = LOCALES.filter((locale) => locale.code !== locale.hreflang)
      .map((locale) => `"${locale.code}": "${locale.hreflang}"`)
      .join(", ");
    expect(PRE_PAINT).toContain(`var hreflang = { ${pairs} };`);
  });

  it("без настроек: светлая тема, фирменная роль, язык и шрифты не трогаются", () => {
    runPrePaint();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.hasAttribute("data-font")).toBe(false);
    expect(document.documentElement.lang).toBe("ru");
    expect(appendedStylesheets()).toEqual([]);
  });

  it("применяет тёмную тему и системную по настройке системы", () => {
    localStorage.setItem("wh.theme", "dark");
    runPrePaint();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    localStorage.setItem("wh.theme", "system");
    stubSystemDark(true);
    runPrePaint();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    stubSystemDark(false);
    runPrePaint();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("ставит роль, язык и подключает объявления шрифтов пары", () => {
    localStorage.setItem("wh.appearance", JSON.stringify({ font: "mono" }));
    localStorage.setItem("wh.lang", "zh");
    runPrePaint();
    expect(document.documentElement.getAttribute("data-font")).toBe("mono");
    expect(document.documentElement.lang).toBe("zh-Hant");
    expect(appendedStylesheets()).toEqual(["/fonts/roles-zh-Hant-mono.css"]);
  });

  it("битая настройка оставляет фирменное оформление", () => {
    localStorage.setItem("wh.appearance", "{не json");
    localStorage.setItem("wh.theme", "неоновая");
    localStorage.setItem("wh.lang", "russian");
    runPrePaint();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.hasAttribute("data-font")).toBe(false);
    expect(appendedStylesheets()).toEqual([]);
  });
});
