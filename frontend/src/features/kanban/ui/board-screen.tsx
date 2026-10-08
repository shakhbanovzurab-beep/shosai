"use client";

import { useEffect, useState } from "react";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { useDismissed } from "@/hooks/use-dismissed";

import type { BoardSummary } from "../domain/board";
import type { BoardsResponse } from "../domain/contract";
import { boardResource, useBoardDetail } from "../model/boards-resource";
import { FirstSync, JiraErrorBanner, WorkspaceTasksOffer } from "./board-banners";
import { BoardProvider, useBoard } from "./board-store";
import { KanbanBoard } from "./kanban-board";
import { type BoardView, KanbanToolbar } from "./kanban-toolbar";
import { TaskListView } from "./task-list-view";
import { TaskTableView } from "./task-table-view";

type ViewProps = {
  boards: BoardSummary[];
  current: BoardSummary;
  workspaceTasks: BoardsResponse["workspace_tasks"];
  view: BoardView;
  onViewChange: (view: BoardView) => void;
};

function BoardBody({ boards, current, workspaceTasks, view, onViewChange }: ViewProps) {
  const { editable, columnOrder, actions } = useBoard();
  const [offerDismissed, dismissOffer] = useDismissed("kanban-workspace-tasks-offer");
  const firstSync = current.jira !== null && current.jira.last_synced_at === null;
  const offer = !offerDismissed && workspaceTasks.board_id === null && workspaceTasks.open > 0 && current.jira === null;
  return (
    <>
      <KanbanToolbar
        boards={boards}
        current={current}
        view={view}
        onViewChange={onViewChange}
        onAddTask={editable && columnOrder[0] ? () => actions.addTask(columnOrder[0]) : undefined}
      />
      <JiraErrorBanner board={current} />
      {offer ? <WorkspaceTasksOffer board={current} open={workspaceTasks.open} onDismiss={dismissOffer} /> : null}
      {firstSync ? <FirstSync board={current} /> : null}
      {!firstSync && view === "board" ? <KanbanBoard /> : null}
      {!firstSync && view !== "board" ? (
        <div className="min-h-0 flex-1 overflow-y-auto bg-muted/25 p-4 lg:p-5">
          {view === "list" ? <TaskListView /> : <TaskTableView />}
        </div>
      ) : null}
    </>
  );
}

function BoardSkeleton() {
  const tc = useTranslations("common");
  return (
    <div className="flex min-h-0 flex-1 gap-4 bg-muted/25 p-4 lg:p-5">
      <span className="sr-only">{tc("feedback.loading")}</span>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-full w-80 shrink-0 rounded-xl" />
      ))}
    </div>
  );
}

/** One board: loads its columns and tasks, and re-reads a Jira board when you come back to the tab. */
export function BoardScreen({ boards, current, workspaceTasks }: Omit<ViewProps, "view" | "onViewChange">) {
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const [view, setView] = useState<BoardView>("board");
  const detail = useBoardDetail(current.id);
  const isJira = current.jira !== null;

  useEffect(() => {
    if (!isJira) return;
    const resource = boardResource(current.id);
    const onVisible = () => (document.visibilityState === "visible" ? void resource.refresh() : undefined);
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [current.id, isJira]);

  if (detail.status !== "ready")
    return (
      <>
        <KanbanToolbar boards={boards} current={current} view={view} onViewChange={setView} />
        {detail.status === "error" ? (
          <div className="p-6">
            <LoadError
              title={t("loadBoardFailed")}
              message={detail.message}
              retryLabel={tc("actions.retry")}
              onRetry={() => void boardResource(current.id).refresh()}
            />
          </div>
        ) : (
          <BoardSkeleton />
        )}
      </>
    );

  // Remounted whenever the server's copy changes (a sync finished, or Jira sent changes).
  return (
    <BoardProvider key={`${current.id}:${detail.data.revision}`} initialDetail={detail.data}>
      <BoardBody boards={boards} current={current} workspaceTasks={workspaceTasks} view={view} onViewChange={setView} />
    </BoardProvider>
  );
}
