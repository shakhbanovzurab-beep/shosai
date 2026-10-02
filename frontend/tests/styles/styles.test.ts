import { existsSync, globSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { describe, expect, it } from "vitest";

import { declaredIn, FRONTEND_ROOT, readStylesheets, syntaxComplaints, withoutComments } from "./stylesheets";

const SOURCE_SHEETS = readStylesheets("src/**/*.css");
const CORE_SHEETS = readStylesheets("src/core/styles/*.css");
const sheet = (name: string): string => CORE_SHEETS.find((one) => one.path.endsWith(`/${name}`))?.text ?? "";

/** Тело блока, открытого на позиции `open` (индекс `{`), без внешних скобок. */
function blockBody(text: string, open: number): string {
  let depth = 0;
  for (let index = open; index < text.length; index += 1) {
    if (text[index] === "{") depth += 1;
    if (text[index] === "}" && --depth === 0) return text.slice(open + 1, index);
  }
  return text.slice(open + 1);
}

const REDUCED_MOTION = "@media (prefers-reduced-motion: reduce)";

/** Селекторы правил с анимацией и селекторы, которые останавливает reduced motion. */
function motionSelectors(css: string): { animated: Set<string>; calmed: Set<string> } {
  let rest = withoutComments(css);
  const calmed = new Set<string>();
  for (let at = rest.indexOf(REDUCED_MOTION); at !== -1; at = rest.indexOf(REDUCED_MOTION)) {
    const open = rest.indexOf("{", at);
    const body = blockBody(rest, open);
    for (const rule of body.matchAll(/([^{}]+)\{[^{}]*animation[^{}]*\}/g)) {
      for (const selector of (rule[1] ?? "").split(",")) calmed.add(selector.trim());
    }
    rest = rest.slice(0, at) + rest.slice(open + body.length + 2);
  }
  const animated = new Set<string>();
  for (const rule of rest.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/(^|[\s;])animation(-name)?\s*:/.test(rule[2] ?? "")) continue;
    for (const selector of (rule[1] ?? "").split(",")) animated.add(selector.trim());
  }
  return { animated, calmed };
}

/** Анимации, которые несут состояние и при reduced motion продолжаются (motion.css). */
const KEEPS_MOVING: ReadonlySet<string> = new Set([".spin"]);

describe("таблицы стилей", () => {
  it("каждая разбирается целиком: комментарии закрыты, скобки сбалансированы", () => {
    const all = [...SOURCE_SHEETS, ...readStylesheets("fonts/*.css")];
    expect(CORE_SHEETS.length).toBeGreaterThanOrEqual(11);
    expect(all.flatMap(syntaxComplaints)).toEqual([]);
  });

  it("каждая ссылка url() ведёт в существующий файл", () => {
    const broken: string[] = [];
    for (const { path, text } of SOURCE_SHEETS) {
      for (const match of withoutComments(text).matchAll(/url\(\s*['"]?([^'")]+?)['"]?\s*\)/g)) {
        const ref = (match[1] ?? "").trim();
        if (/^(data:|#)/.test(ref)) continue;
        const file = ref.startsWith("/fonts/")
          ? join(FRONTEND_ROOT, ref.slice(1))
          : join(FRONTEND_ROOT, dirname(path), ref);
        if (ref.startsWith("http") || !existsSync(file)) broken.push(`${path}: url(${ref})`);
      }
    }
    expect(broken).toEqual([]);
  });

  it("светлая и тёмная темы объявляют одни и те же токены", () => {
    const light = declaredIn(sheet("tokens-light.css"), /html\[data-theme="light"\]/);
    const dark = declaredIn(sheet("tokens-dark.css"), /html\[data-theme="dark"\]/);
    const shared = declaredIn(sheet("tokens.css"), /^:root$/);
    expect(light.size).toBeGreaterThan(50);
    expect([...dark].filter((name) => !light.has(name) && !shared.has(name))).toEqual([]);
    expect([...light].filter((name) => !dark.has(name))).toEqual([]);
  });

  it("каждая переменная, которую читают стили, где-то объявлена", () => {
    const declared = new Set(CORE_SHEETS.flatMap(({ text }) => [...declaredIn(text, /[\s\S]*/)]));
    const missing = CORE_SHEETS.flatMap(({ path, text }) =>
      [...withoutComments(text).matchAll(/var\((--[\w-]+)/g)]
        .map((match) => match[1] ?? "")
        .filter((name) => !declared.has(name) && !name.startsWith("--tw-"))
        .map((name) => `${path}: ${name}`),
    );
    expect(missing).toEqual([]);
  });

  it("у каждой анимации есть поведение при prefers-reduced-motion", () => {
    const uncovered = CORE_SHEETS.flatMap(({ path, text }) => {
      const { animated, calmed } = motionSelectors(text);
      return [...animated].filter((one) => !calmed.has(one) && !KEEPS_MOVING.has(one)).map((one) => `${path}: ${one}`);
    });
    expect(uncovered).toEqual([]);
    expect(motionSelectors(sheet("motion.css")).calmed).toContain(".ticker");
  });

  it("кегли объявлены в rem, а не в пикселях: системное увеличение текста работает везде", () => {
    const offenders = globSync("src/**/*.{ts,tsx,css}", { cwd: FRONTEND_ROOT }).flatMap((path) =>
      [...readFileSync(join(FRONTEND_ROOT, path), "utf8").matchAll(/text-\[\d+(?:\.\d+)?px\]|font-size:\s*\d+(?:\.\d+)?px/g)]
        .map((match) => `${path}: ${match[0]}`),
    );
    expect(offenders).toEqual([]);
  });

  it("preflight не подключён: слои Tailwind импортируются поштучно", () => {
    const main = sheet("main.css");
    expect(main).toContain('@import "tailwindcss/theme.css" layer(theme);');
    expect(withoutComments(main)).not.toMatch(/@import\s+"tailwindcss"\s*;|preflight/);
  });
});
