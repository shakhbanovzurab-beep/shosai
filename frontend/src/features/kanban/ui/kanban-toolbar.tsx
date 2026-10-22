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
  /** Поиск и фильтры доски — в той же строке, сразу за выбором вида; их нет, пока доска грузится. */
  filters?: ReactNode;
  /** Действия доски перед «Добавить задачу» (кнопка «Поля»); их нет, пока доска грузится. */
  children?: ReactNode;
};

/**
 * Одна строка над доской: выбор доски и вида, поиск и фильтры, статус синхронизации с Jira, действия доски и
 * «Добавить задачу». Фильтры занимают оставшееся место и листаются вбок, если не помещаются. Кнопок без действия
 * здесь нет.
 */
export function KanbanToolbar({
  boards,
  current,
  view,
  onViewChange,
  onAddTask,
  filters,
  children,
}: KanbanToolbarProps) {
  const t = useTranslations("kanban");
  return (
    <div className="flex shrink-0 flex-col gap-3 border-b px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center lg:flex-1">
        {/* Заголовок страницы — имя доски; на экране его показывает переключатель досок. */}
        <h1 className="sr-only">{current.name}</h1>
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
        {filters}
      </div>

      <div className="flex min-w-0 shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
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
