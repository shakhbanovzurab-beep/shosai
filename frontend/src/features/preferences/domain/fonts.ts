/** The fonts a user can pick, in menu order. `ui/fonts.ts` loads each one with next/font. */
const FONT_LABELS = {
  geist: "Geist",
  inter: "Inter",
  notoSans: "Noto Sans",
  nunitoSans: "Nunito Sans",
  figtree: "Figtree",
  roboto: "Roboto",
  raleway: "Raleway",
  dmSans: "DM Sans",
  publicSans: "Public Sans",
  outfit: "Outfit",
  geistMono: "Geist Mono",
  geistPixelSquare: "Geist Pixel Square",
  jetBrainsMono: "JetBrains Mono",
  notoSerif: "Noto Serif",
  robotoSlab: "Roboto Slab",
  merriweather: "Merriweather",
  lora: "Lora",
  playfairDisplay: "Playfair Display",
} as const;

export type FontKey = keyof typeof FONT_LABELS;

export const fontKeys = Object.keys(FONT_LABELS) as FontKey[];

export const fontOptions = fontKeys.map((key) => ({
  key,
  label: FONT_LABELS[key],
}));
