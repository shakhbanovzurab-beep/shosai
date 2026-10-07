export type RGB = [number, number, number];

export const FG_FALLBACK: RGB = [23, 23, 23];
export const BG_FALLBACK: RGB = [255, 255, 255];

export const mixRGB = (a: RGB, b: RGB, t: number): RGB => [
  a[0] + (b[0] - a[0]) * t,
  a[1] + (b[1] - a[1]) * t,
  a[2] + (b[2] - a[2]) * t,
];

export const luminance = (c: RGB): number => (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;

export const rgbString = (r: number, g: number, b: number) => `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})`;

export const rgbaString = (c: RGB, a: number) =>
  `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${a.toFixed(3)})`;

/** How far each activity level sits between the empty-day colour and the theme's primary. */
const LEVEL_MIX = [0.3, 0.52, 0.76, 1];

/**
 * Level 0 is a faint tint of the foreground; levels 1–4 ramp from there up to the primary
 * colour, so every preset and mode gets its own scale.
 */
export const levelColors = (fg: RGB, bg: RGB, primary: RGB, dark: boolean): RGB[] => {
  const empty = mixRGB(bg, fg, dark ? 0.11 : 0.075);
  return [empty, ...LEVEL_MIX.map((t) => mixRGB(empty, primary, t))];
};
