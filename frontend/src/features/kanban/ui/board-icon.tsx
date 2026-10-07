import { cn } from "cn";
import { siJira } from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

import type { BoardSummary } from "../domain/board";
import { BOARD_ICON_GLYPHS } from "./board-icons";

/** A board's mark: the Jira logo for a synced board, otherwise its chosen icon. */
export function BoardGlyph({ board, className }: { board: Pick<BoardSummary, "icon" | "jira">; className?: string }) {
  if (board.jira)
    return (
      <SimpleIcon
        icon={siJira}
        aria-hidden="true"
        className={cn("size-4 fill-blue-600 dark:fill-blue-400", className)}
      />
    );
  const Icon = BOARD_ICON_GLYPHS[board.icon];
  return <Icon className={cn("size-4", className)} aria-hidden="true" />;
}
