"use client";

import {
  ArrowUpDown,
  Bot,
  ChevronDown,
  Kanban as KanbanIcon,
  LayoutTemplate,
  List,
  type LucideIcon,
  Plus,
  SlidersHorizontal,
  Table2,
  Upload,
} from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { ButtonGroup, ButtonGroupSeparator } from "@/components/ui/button-group";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import type { BoardSummary } from "../domain/board";
import { BoardControls } from "./board-controls";
import { JiraSyncStatus } from "./jira-sync-status";

export type BoardView = "board" | "list" | "table";

const VIEWS: { view: BoardView; icon: LucideIcon }[] = [
  { view: "board", icon: KanbanIcon },
  { view: "list", icon: List },
  { view: "table", icon: Table2 },
];

type KanbanToolbarProps = {
  boards: BoardSummary[];
  current: BoardSummary;
  view: BoardView;
  onViewChange: (view: BoardView) => void;
  /** Adds to the first column; undefined while the board can't be edited. */
  onAddTask?: () => void;
};

/** The board switcher and view tabs, Jira sync status, filter and sort, and "Add task". */
export function KanbanToolbar({ boards, current, view, onViewChange, onAddTask }: KanbanToolbarProps) {
  const t = useTranslations("kanban");
  return (
    <div className="flex shrink-0 flex-col gap-3 border-b px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
        <BoardControls boards={boards} current={current} />
        <Tabs value={view} onValueChange={(v) => onViewChange(v as BoardView)} className="min-w-0">
          <TabsList
            aria-label={t("views.label")}
            className="w-full *:data-[slot=tabs-trigger]:flex-1 sm:w-fit sm:*:data-[slot=tabs-trigger]:flex-none"
          >
            {VIEWS.map(({ view: value, icon: Icon }) => (
              <TabsTrigger key={value} value={value} className="gap-2">
                <Icon />
                {t(`views.${value}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center 2xl:justify-end">
        <JiraSyncStatus board={current} />
        <Button variant="outline" className="w-full sm:w-auto">
          <SlidersHorizontal data-icon="inline-start" />
          {t("toolbar.filter")}
        </Button>
        <Button variant="outline" className="w-full sm:w-auto">
          <ArrowUpDown data-icon="inline-start" />
          {t("toolbar.sort")}
        </Button>
        <ButtonGroup className="w-full sm:w-fit">
          <Button className="flex-1 sm:flex-none" disabled={!onAddTask} onClick={onAddTask}>
            <Plus data-icon="inline-start" />
            {t("addTask")}
          </Button>
          <ButtonGroupSeparator />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button aria-label={t("toolbar.moreWaysToAdd")} disabled={!onAddTask}>
                <ChevronDown />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem>
                <Upload />
                {t("toolbar.importCsv")}
              </DropdownMenuItem>
              <DropdownMenuItem>
                <LayoutTemplate />
                {t("toolbar.addFromTemplate")}
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Bot />
                {t("toolbar.createAutomation")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </ButtonGroup>
      </div>
    </div>
  );
}
