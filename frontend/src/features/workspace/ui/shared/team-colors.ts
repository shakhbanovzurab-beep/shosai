import type { TeamColor } from "../../domain/contract";

// Team accents use Tailwind's named palette: the theme has no tokens for categorical colours.
export const TEAM_DOT_CLASSES: Record<TeamColor, string> = {
  blue: "bg-blue-500",
  green: "bg-green-500",
  amber: "bg-amber-500",
  violet: "bg-violet-500",
  rose: "bg-rose-500",
  sky: "bg-sky-500",
};
