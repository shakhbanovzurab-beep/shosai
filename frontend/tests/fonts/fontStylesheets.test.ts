import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  faceSheetPath,
  findDrift,
  hreflangOf,
  parseFaces,
  renderFontStylesheets,
  ROLE_RULES_PATH,
} from "../../scripts/fonts/render.ts";
import { LOCALES } from "@/core/i18n/locales";
import { FONT_CONFIG, FONT_LOCALES, FONT_ROLES } from "@/core/theme/fontCatalogue";

const FRONTEND_ROOT = join(import.meta.dirname, "../..");
const FONTS_DIR = join(FRONTEND_ROOT, "fonts");
const faces = parseFaces(JSON.parse(readFileSync(join(FONTS_DIR, "faces.json"), "utf8")));
const rendered = renderFontStylesheets(faces);

const readExisting = (path: string): string | null => {
  const file = join(FRONTEND_ROOT, path);
  return existsSync(file) ? readFileSync(file, "utf8") : null;
};

describe("таблицы стилей шрифтов", () => {
  it("на диске ровно то, что генератор строит из каталога (npm run fonts -- --check)", () => {
    expect(rendered.size).toBe(1 + FONT_LOCALES.length * FONT_ROLES.length);
    expect(findDrift(rendered, readExisting)).toEqual([]);
  });

  it("сверка замечает правку руками и пропавший файл", () => {
    const planted = new Map([
      [ROLE_RULES_PATH, `${readExisting(ROLE_RULES_PATH) ?? ""}/* правка */\n`],
      [faceSheetPath("ru", "mono"), readExisting(faceSheetPath("ru", "mono")) ?? ""],
    ]);
    const missing = (path: string): string | null => (path === faceSheetPath("ru", "mono") ? null : readExisting(path));
    expect(findDrift(planted, missing)).toEqual([ROLE_RULES_PATH, faceSheetPath("ru", "mono")]);
  });

  it("каждый сгенерированный файл помечен @generated в первых пяти строках", () => {
    for (const text of rendered.values()) {
      expect(text.split("\n").slice(0, 5).join("\n")).toContain("@generated");
    }
  });

  it("каждый url() ведёт в перенесённый файл, и каждый woff2 кем-то используется", () => {
    const vendored = new Set(readdirSync(FONTS_DIR).filter((name) => name.endsWith(".woff2")));
    const referenced = new Set<string>();
    for (const [path, text] of rendered) {
      for (const match of text.matchAll(/url\('([^']+)'\)/g)) {
        const url = match[1] ?? "";
        expect(url, `${path}: адрес вне /fonts/`).toMatch(/^\/fonts\/[^/]+\.woff2$/);
        referenced.add(url.slice("/fonts/".length));
      }
    }
    expect([...referenced].filter((name) => !vendored.has(name))).toEqual([]);
    expect([...vendored].filter((name) => !referenced.has(name))).toEqual([]);
    expect(vendored.size).toBeGreaterThan(1000);
  });

  it("в файле пары объявлены ровно семейства её роли", () => {
    for (const locale of FONT_LOCALES) {
      for (const role of FONT_ROLES) {
        const text = rendered.get(faceSheetPath(hreflangOf(locale), role)) ?? "";
        const declared = new Set([...text.matchAll(/font-family:'([^']+)'/g)].map((match) => match[1]));
        expect([...declared].toSorted()).toEqual(FONT_CONFIG[locale][role].hosted.toSorted());
      }
    }
  });

  it("разбор манифеста отвергает запись неверной формы", () => {
    expect(() => parseFaces({})).toThrow("ожидается список");
    expect(() => parseFaces([{ family: "Onest", file: "x.woff2", range: "U+0", style: "normal" }])).toThrow(
      "запись 0",
    );
  });
});

describe("каталог шрифтов", () => {
  it("знает ровно языки реестра локалей; китайский адресуется как zh-Hant", () => {
    expect(FONT_LOCALES.toSorted()).toEqual(LOCALES.map((locale) => locale.code).toSorted());
    expect(hreflangOf("zh")).toBe("zh-Hant");
    const rules = rendered.get(ROLE_RULES_PATH) ?? "";
    expect(rules).toContain('html[lang="zh-Hant"][data-font="sans"]');
    expect(rules).not.toContain('html[lang="zh"]');
  });

  it("у каждого языка пять ролей с пятью разными лицами, и первой стоит наша гарнитура", () => {
    for (const locale of FONT_LOCALES) {
      const set = FONT_CONFIG[locale];
      const first = FONT_ROLES.map((role) => set[role].stack.split(",")[0]?.trim());
      expect(new Set(first).size, `${locale}: ${first.join(" / ")}`).toBe(FONT_ROLES.length);
      for (const role of FONT_ROLES) {
        if (role === "native") continue;
        expect(set[role].stack.startsWith('"'), `${locale}/${role}`).toBe(true);
        expect(set[role].hosted.length, `${locale}/${role}`).toBeGreaterThan(0);
      }
    }
  });

  it("каждая раздаваемая гарнитура есть в манифесте", () => {
    const served = new Set(faces.map((face) => face.family));
    for (const locale of FONT_LOCALES) {
      for (const role of FONT_ROLES) {
        for (const family of FONT_CONFIG[locale][role].hosted) {
          expect(served.has(family), `${locale}/${role}: ${family}`).toBe(true);
        }
      }
    }
  });

  it("заголовки фирменной роли набраны Unbounded на всех языках", () => {
    const rules = rendered.get(ROLE_RULES_PATH) ?? "";
    for (const locale of FONT_LOCALES) {
      const block = rules.slice(rules.indexOf(`html[lang="${hreflangOf(locale)}"],`));
      expect(/--ui-head:\s*([^;]+);/.exec(block)?.[1], locale).toMatch(/^"Unbounded"/);
    }
  });
});
