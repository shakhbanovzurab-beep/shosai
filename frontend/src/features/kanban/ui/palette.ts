import type { Color } from "../domain/stickers-contract";

/*
 * Палитра колонок и состояний: имя цвета из API → классы Tailwind. Общих категориальных токенов у темы нет,
 * поэтому, как в Notes и пространствах, берутся именованные цвета палитры Tailwind (AGENTS.md); точка и полоса
 * читаются и в светлой, и в тёмной теме.
 */

type Swatch = { dot: string; rule: string };

export const SWATCHES: Record<Color, Swatch> = {
  gray: { dot: "bg-zinc-400", rule: "border-t-zinc-400" },
  red: { dot: "bg-red-500", rule: "border-t-red-500" },
  orange: { dot: "bg-orange-500", rule: "border-t-orange-500" },
  amber: { dot: "bg-amber-500", rule: "border-t-amber-500" },
  green: { dot: "bg-emerald-500", rule: "border-t-emerald-500" },
  teal: { dot: "bg-teal-500", rule: "border-t-teal-500" },
  blue: { dot: "bg-blue-500", rule: "border-t-blue-500" },
  violet: { dot: "bg-violet-500", rule: "border-t-violet-500" },
  pink: { dot: "bg-pink-500", rule: "border-t-pink-500" },
};
