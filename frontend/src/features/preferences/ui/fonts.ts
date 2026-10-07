import {
  DM_Sans,
  Figtree,
  Geist,
  Geist_Mono,
  Inter,
  JetBrains_Mono,
  Lora,
  Merriweather,
  Noto_Sans,
  Noto_Serif,
  Nunito_Sans,
  Outfit,
  Playfair_Display,
  Public_Sans,
  Raleway,
  Roboto,
  Roboto_Slab,
} from "next/font/google";

import { GeistPixelSquare } from "geist/font/pixel";

import type { FontKey } from "../domain/fonts";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const notoSans = Noto_Sans({
  subsets: ["latin"],
  variable: "--font-noto-sans",
});

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-roboto",
});

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

const nunitoSans = Nunito_Sans({
  subsets: ["latin"],
  variable: "--font-nunito-sans",
});

const figtree = Figtree({
  subsets: ["latin"],
  variable: "--font-figtree",
});

const raleway = Raleway({
  subsets: ["latin"],
  variable: "--font-raleway",
});

const publicSans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-public-sans",
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

const notoSerif = Noto_Serif({
  subsets: ["latin"],
  variable: "--font-noto-serif",
});

const robotoSlab = Roboto_Slab({
  subsets: ["latin"],
  variable: "--font-roboto-slab",
});

const merriweather = Merriweather({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-merriweather",
});

const lora = Lora({
  subsets: ["latin"],
  variable: "--font-lora",
});

const playfairDisplay = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair-display",
});

/** One next/font loader per font key; their CSS variables go on <body> so any of them can be applied. */
const fonts: Record<FontKey, { variable: string }> = {
  geist,
  inter,
  notoSans,
  nunitoSans,
  figtree,
  roboto,
  raleway,
  dmSans,
  publicSans,
  outfit,
  geistMono,
  geistPixelSquare: GeistPixelSquare,
  jetBrainsMono,
  notoSerif,
  robotoSlab,
  merriweather,
  lora,
  playfairDisplay,
};

export const fontVars = Object.values(fonts)
  .map((font) => font.variable)
  .join(" ");
