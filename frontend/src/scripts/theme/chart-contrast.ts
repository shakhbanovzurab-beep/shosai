import { readFileSync } from "node:fs";
import path from "node:path";

/*
 * Контраст цветов графиков темы: каждый --chart-* должен отличаться от --background и --card не меньше чем на
 * 3:1 (WCAG для неглавной графики) в светлом и тёмном режиме темы по умолчанию и каждого пресета. Значения —
 * oklch; каскад как в браузере: пресет поверх темы по умолчанию, в тёмном режиме светлый блок пресета сильнее `.dark`.
 */

type Oklch = readonly [number, number, number];
type Tokens = Record<string, Oklch>;

const ROOT = path.resolve(import.meta.dirname, "../../..");
const DEFAULT_FILE = path.join(ROOT, "src/app/globals.css");
const PRESET_DIR = path.join(ROOT, "src/styles/presets");
export const MIN_CONTRAST = 3;
const CHARTS = [1, 2, 3, 4, 5].map((n) => `chart-${n}`);
const SURFACES = ["background", "card"];

function blocks(css: string): { selector: string; body: string }[] {
  return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, selector = "", body = ""]) => ({
    selector: (selector.split("*/").pop() ?? "").trim(),
    body,
  }));
}

function tokens(css: string, matches: (selector: string) => boolean): Tokens {
  const found: Tokens = {};
  for (const block of blocks(css).filter((b) => matches(b.selector))) {
    for (const [, name = "", L, C, h] of block.body.matchAll(
      /--([\w-]+):\s*oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/g,
    )) {
      found[name] = [Number(L), Number(C), Number(h)];
    }
  }
  return found;
}

function linear([L, C, h]: Oklch): number[] {
  const a = C * Math.cos((h * Math.PI) / 180);
  const b = C * Math.sin((h * Math.PI) / 180);
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ].map((x) => Math.min(1, Math.max(0, x)));
}

function luminance(color: Oklch): number {
  const [r = 0, g = 0, b = 0] = linear(color);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(one: Oklch, other: Oklch): number {
  const [light, dark] = [luminance(one), luminance(other)].sort((x, y) => y - x);
  return ((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05);
}

/** Тема по умолчанию и пресеты, каждый в двух режимах, с итоговыми токенами после каскада. */
export function themeModes(): { name: string; tokens: Tokens }[] {
  const base = readFileSync(DEFAULT_FILE, "utf8");
  const light = tokens(base, (s) => s === ":root");
  const dark = { ...light, ...tokens(base, (s) => s === ".dark") };
  const modes = [
    { name: "default light", tokens: light },
    { name: "default dark", tokens: dark },
  ];
  for (const file of presetFiles()) {
    const css = readFileSync(path.join(PRESET_DIR, file), "utf8");
    const preset = tokens(css, (s) => s.startsWith(":root[data-theme-preset"));
    const presetDark = tokens(css, (s) => s.startsWith(".dark"));
    const name = file.replace(/\.css$/, "");
    modes.push({ name: `${name} light`, tokens: { ...light, ...preset } });
    modes.push({ name: `${name} dark`, tokens: { ...dark, ...preset, ...presetDark } });
  }
  return modes;
}

// Пресеты — те, что тема по умолчанию импортирует, в её порядке.
function presetFiles(): string[] {
  return (readFileSync(DEFAULT_FILE, "utf8").match(/presets\/[\w-]+\.css/g) ?? []).map((ref) => ref.slice(8));
}

/** Пары «тема, токен, поверхность», где контраст ниже 3:1, с его значением. */
export function lowContrast(): string[] {
  const problems: string[] = [];
  for (const { name, tokens: values } of themeModes()) {
    for (const chart of CHARTS) {
      for (const surface of SURFACES) {
        const color = values[chart];
        const behind = values[surface];
        if (!color || !behind) {
          problems.push(`${name}: нет --${chart} или --${surface}`);
          continue;
        }
        const ratio = contrast(color, behind);
        if (ratio < MIN_CONTRAST) problems.push(`${name}: --${chart} к --${surface} ${ratio.toFixed(2)}:1`);
      }
    }
  }
  return problems;
}
