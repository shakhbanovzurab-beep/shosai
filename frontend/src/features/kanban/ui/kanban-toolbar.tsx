"use client";

import type { ReactNode } from "react";

import { Kanban as KanbanIcon, List, type LucideIcon, Plus, Table2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import type { BoardSummary } from "../domain/boards-contract";
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
  /** Добавляет в первую колонку; undefined, пока доску нельзя менять. */
  onAddTask?: () => void;
  /** Действия доски перед «Добавить задачу» (кнопка «Поля»); их нет, пока доска грузится. */
  children?: ReactNode;
};

/** Выбор доски и вида, статус синхронизации с Jira, действия доски и «Добавить задачу». Кнопок без действия здесь нет. */
export function KanbanToolbar({ boards, current, view, onViewChange, onAddTask, children }: KanbanToolbarProps) {
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
        {children}
        <Button className="w-full sm:w-auto" disabled={!onAddTask} onClick={onAddTask}>
          <Plus data-icon="inline-start" />
          {t("addTask")}
        </Button>
      </div>
    </div>
  );
}
