import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_APPEARANCE, normalizeAppearance } from "@/core/theme/appearance";
import { applyAppearance, readStoredAppearance, storeAppearance } from "@/core/theme/appearanceDocument";
import { ensureFontFaces } from "@/core/theme/fontFaces";

const stylesheets = (): string[] =>
  [...document.head.querySelectorAll('link[rel="stylesheet"]')].map((link) => link.getAttribute("href") ?? "");

describe("разбор оформления", () => {
  it("повреждённый вход даёт фирменное оформление, а не поломку", () => {
    const junk: unknown[] = [null, undefined, 42, "серифный", [], { font: "неоновый" }, { font: 7 }];
    for (const input of junk) expect(normalizeAppearance(input)).toEqual(DEFAULT_APPEARANCE);
    // Имена свойств прототипа — не роли.
    expect(normalizeAppearance({ font: "constructor" })).toEqual(DEFAULT_APPEARANCE);
    expect(normalizeAppearance({ font: "toString" })).toEqual(DEFAULT_APPEARANCE);
  });

  it("читает роль, игнорируя лишние поля, и переводит прежние имена", () => {
    expect(normalizeAppearance({ theme: "dark", accent: "red", font: "mono" })).toEqual({ font: "mono" });
    expect(normalizeAppearance({ font: "alt" })).toEqual({ font: "sans" });
    expect(normalizeAppearance({ font: "system" })).toEqual({ font: "native" });
  });
});

describe("оформление на документе", () => {
  beforeEach(() => {
    localStorage.clear();
    document.head.replaceChildren();
    document.documentElement.lang = "ru";
    document.documentElement.removeAttribute("data-font");
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("фирменная роль снимает атрибут, другая — ставит и подключает свои шрифты", () => {
    applyAppearance({ font: "serif" });
    expect(document.documentElement.getAttribute("data-font")).toBe("serif");
    expect(stylesheets()).toEqual(["/fonts/roles-ru-serif.css"]);
    applyAppearance(DEFAULT_APPEARANCE);
    expect(document.documentElement.hasAttribute("data-font")).toBe(false);
    expect(stylesheets()).toEqual(["/fonts/roles-ru-serif.css", "/fonts/roles-ru-whisperer.css"]);
  });

  it("хранит выбор в wh.appearance и переживает битый JSON и недоступное хранилище", () => {
    storeAppearance({ font: "native" });
    expect(localStorage.getItem("wh.appearance")).toBe('{"font":"native"}');
    expect(readStoredAppearance()).toEqual({ font: "native" });
    localStorage.setItem("wh.appearance", "{не json");
    expect(readStoredAppearance()).toEqual(DEFAULT_APPEARANCE);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("заблокировано", "SecurityError");
    });
    expect(readStoredAppearance()).toEqual(DEFAULT_APPEARANCE);
  });

  it("подключает объявления пары один раз, без языка — ничего, сбой загрузки снимает ссылку", () => {
    ensureFontFaces("ja", "sans");
    ensureFontFaces("ja", "sans");
    ensureFontFaces("", "sans");
    expect(stylesheets()).toEqual(["/fonts/roles-ja-sans.css"]);
    document.head.querySelector("link")?.dispatchEvent(new Event("error"));
    expect(stylesheets()).toEqual([]);
    ensureFontFaces("ja", "sans");
    expect(stylesheets()).toEqual(["/fonts/roles-ja-sans.css"]);
  });
});
