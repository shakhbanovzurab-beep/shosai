import type { NoteFolderColor } from "../domain/types";

// Folder accents use Tailwind's named palette: the theme has no tokens for categorical colours.
export const FOLDER_DOT_CLASSES: Record<NoteFolderColor, string> = {
  red: "bg-red-500",
  blue: "bg-blue-500",
  amber: "bg-amber-500",
  green: "bg-green-500",
  violet: "bg-violet-500",
};
