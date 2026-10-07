import type { UrgencyTier } from "../../domain/urgency";

/*
 * Urgency is its own scale, apart from the brand accent: Tailwind's named palette, since the theme
 * has no tokens for it. It is never colour alone: the bar's line style follows the tier (solid,
 * double, dashed, dotted) and every gap kind has its own icon next to its words.
 */

export const BAR: Record<UrgencyTier, string> = {
  critical: "border-s-4 border-solid border-red-500 dark:border-red-400",
  soon: "border-s-4 border-double border-amber-500 dark:border-amber-400",
  stale: "border-s-2 border-dashed border-sky-600 dark:border-sky-400",
  quiet: "border-s-2 border-dotted border-zinc-400 dark:border-zinc-500",
};

export const INK: Record<UrgencyTier, string> = {
  critical: "text-red-600 dark:text-red-400",
  soon: "text-amber-700 dark:text-amber-400",
  stale: "text-sky-700 dark:text-sky-400",
  quiet: "text-muted-foreground",
};

/** A quiet warning ahead of a refusal (no board): the "soon" ink, never the brand accent. */
export const WARNING_INK = INK.soon;
