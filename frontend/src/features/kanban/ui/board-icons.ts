import {
  BookOpen,
  Briefcase,
  Dumbbell,
  GraduationCap,
  Heart,
  House,
  type LucideIcon,
  Plane,
  Rocket,
  ShoppingCart,
  User,
} from "lucide-react";

import type { BoardIcon } from "../domain/board";

/* The icons a board can have, with the name each one stands for. */

export const BOARD_ICON_GLYPHS: Record<BoardIcon, LucideIcon> = {
  briefcase: Briefcase,
  home: House,
  user: User,
  heart: Heart,
  "graduation-cap": GraduationCap,
  plane: Plane,
  "shopping-cart": ShoppingCart,
  dumbbell: Dumbbell,
  rocket: Rocket,
  book: BookOpen,
};

/** What each icon stands for: its key in the `kanbanBoards.icons` catalog. */
export const BOARD_ICON_NAMES = {
  briefcase: "work",
  home: "home",
  user: "personal",
  heart: "health",
  "graduation-cap": "study",
  plane: "travel",
  "shopping-cart": "shopping",
  dumbbell: "fitness",
  rocket: "project",
  book: "reading",
} as const satisfies Record<BoardIcon, string>;
