import { BG_FALLBACK, FG_FALLBACK, levelColors, luminance, type RGB } from "../../../domain/skyline/colors";

// Any CSS colour → sRGB, by letting the browser paint it. Handles oklch, color-mix, names…
let probe: CanvasRenderingContext2D | null = null;
export const toRGB = (color: string, fallback: RGB | null): RGB | null => {
  if (!probe) {
    const c = document.createElement("canvas");
    c.width = 1;
    c.height = 1;
    probe = c.getContext("2d", { willReadFrequently: true });
  }
  if (!probe || !color) return fallback;
  probe.clearRect(0, 0, 1, 1);
  probe.fillStyle = "rgba(0,0,0,0)";
  probe.fillStyle = color;
  probe.fillRect(0, 0, 1, 1);
  const d = probe.getImageData(0, 0, 1, 1).data;
  if (d[3] < 8) return fallback;
  return [d[0], d[1], d[2]];
};

export type ThemeColors = { fg: RGB; bg: RGB; dark: boolean; font: string; levels: RGB[] };

/**
 * Reads the active theme preset off the element: foreground, background and
 * `--primary`. Level 0 is a faint tint of the foreground; levels 1–4 ramp from
 * there up to the primary colour, so every preset and mode gets its own scale.
 */
export const readThemeColors = (el: HTMLElement): ThemeColors => {
  const cs = getComputedStyle(el);
  const fg = toRGB(cs.color, FG_FALLBACK) ?? FG_FALLBACK;
  const bg = toRGB(cs.backgroundColor, null) ?? (luminance(fg) > 0.5 ? [10, 10, 10] : BG_FALLBACK);
  const dark = luminance(bg) < 0.45;
  const primary = toRGB(cs.getPropertyValue("--primary").trim(), fg) ?? fg;
  const levels = levelColors(fg, bg, primary, dark);
  return { fg, bg, dark, font: `400 10px ${cs.fontFamily || "sans-serif"}`, levels };
};
