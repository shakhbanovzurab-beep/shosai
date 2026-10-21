"use client";

import { Check, ChevronsUpDown, Palette, Pencil, Plus, Trash2, Unlink } from "lucide-react";
import { siJira } from "simple-icons";
import { useFormatter, useTranslations } from "use-intl";

import { SimpleIcon } from "@/components/simple-icon";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DropdownMenuCheckboxItem,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu-items";
import { DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from "@/components/ui/dropdown-menu-sub";
import { Link } from "@/lib/navigation";

import { BOARD_ICONS, boardHref } from "../domain/board";
import type { BoardSummary } from "../domain/boards-contract";
import { chooseIncomingBoard, updateBoard } from "../model/board-actions";
import { BoardGlyph } from "./board-icon";
import { BOARD_ICON_GLYPHS, BOARD_ICON_NAMES } from "./board-icons";

export type BoardMenuIntent = "new" | "jira" | "rename" | "delete";

function BoardItems({ boards, current }: { boards: BoardSummary[]; current: BoardSummary }) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  return boards.map((board) => (
    <DropdownMenuItem key={board.id} asChild>
      <Link href={boardHref(board.id)} aria-current={board.id === current.id ? "page" : undefined}>
        <BoardGlyph board={board} />
        <span dir="auto" className="min-w-0 flex-1 truncate">
          {board.name}
        </span>
        <span className="text-muted-foreground text-xs tabular-nums" aria-hidden="true">
          {format.number(board.task_count)}
        </span>
        <span className="sr-only">{t("taskCount", { count: board.task_count })}</span>
        <Check className={board.id === current.id ? undefined : "invisible"} />
      </Link>
    </DropdownMenuItem>
  ));
}

/** The board name in the toolbar, opening the list of boards and what can be done with them. */
export function BoardSwitcher({
  boards,
  current,
  onIntent,
}: {
  boards: BoardSummary[];
  current: BoardSummary;
  onIntent: (intent: BoardMenuIntent) => void;
}) {
  const t = useTranslations("kanbanBoards");
  const ta = useTranslations("kanbanApi");
  const appBoards = boards.filter((b) => !b.jira);
  const jiraBoards = boards.filter((b) => b.jira);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="-ms-2 min-w-0 max-w-full gap-2 px-2 font-semibold text-base">
          <BoardGlyph board={current} />
          <span dir="auto" className="truncate">
            {current.name}
          </span>
          <ChevronsUpDown className="text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="text-muted-foreground text-xs">{t("switcher.boards")}</DropdownMenuLabel>
        <DropdownMenuGroup>
          <BoardItems boards={appBoards} current={current} />
        </DropdownMenuGroup>
        {jiraBoards.length > 0 ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-muted-foreground text-xs">{t("switcher.jiraBoards")}</DropdownMenuLabel>
            <DropdownMenuGroup>
              <BoardItems boards={jiraBoards} current={current} />
            </DropdownMenuGroup>
          </>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={() => onIntent("new")}>
            <Plus />
            {t("switcher.newBoard")}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onIntent("jira")}>
            <SimpleIcon icon={siJira} aria-hidden="true" className="size-4 fill-current" />
            {t("switcher.syncJiraBoard")}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={() => onIntent("rename")}>
            <Pencil />
            {t("switcher.rename")}
          </DropdownMenuItem>
          {current.jira ? null : (
            <DropdownMenuCheckboxItem
              checked={current.incoming}
              onCheckedChange={(on) =>
                void chooseIncomingBoard(on === true ? current.id : null, current.name, { t, ta })
              }
            >
              {t("switcher.incoming")}
            </DropdownMenuCheckboxItem>
          )}
          {current.jira ? null : (
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Palette />
                {t("switcher.changeIcon")}
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-44">
                {BOARD_ICONS.map((icon) => {
                  const Icon = BOARD_ICON_GLYPHS[icon];
                  return (
                    <DropdownMenuItem key={icon} onSelect={() => void updateBoard(current.id, { icon }, { t, ta })}>
                      <Icon />
                      {t(`icons.${BOARD_ICON_NAMES[icon]}`)}
                      <Check className={icon === current.icon ? "ms-auto" : "invisible ms-auto"} />
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          )}
          <DropdownMenuItem variant="destructive" onSelect={() => onIntent("delete")}>
            {current.jira ? <Unlink /> : <Trash2 />}
            {current.jira ? t("switcher.stopSyncing") : t("switcher.delete")}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
