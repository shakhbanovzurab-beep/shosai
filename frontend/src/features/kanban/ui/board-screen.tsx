"use client";

import { useEffect, useState } from "react";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { useDismissed } from "@/hooks/use-dismissed";

import type { BoardSummary, BoardsResponse } from "../domain/boards-contract";
import { useColumnOrder } from "../model/board-hooks";
import { boardResource, useBoardDetail } from "../model/boards-resource";
import { FirstSync, IncomingOffer, JiraErrorBanner } from "./board-banners";
import { BoardProvider, useBoardCommands, useEditable } from "./board-store";
import { FieldsButton } from "./fields/fields-sheet";
import { FilterBar } from "./filters/filter-bar";
import { NoMatches } from "./filters/no-matches";
import { useShownCount } from "./filters/use-visible-cards";
import { KanbanBoard } from "./kanban-board";
import { type BoardView, KanbanToolbar } from "./kanban-toolbar";
import { TaskPanel } from "./panel/task-panel";
import { TaskListView } from "./task-list-view";
import { TaskTableView } from "./task-table-view";

type ViewProps = {
  boards: BoardSummary[];
  current: BoardSummary;
  incoming: BoardsResponse["incoming"];
  view: BoardView;
  onViewChange: (view: BoardView) => void;
};

function BoardBody({ boards, current, incoming, view, onViewChange }: ViewProps) {
  const editable = useEditable();
  const columnOrder = useColumnOrder();
  const { cards } = useBoardCommands();
  const [offerDismissed, dismissOffer] = useDismissed("kanban-workspace-tasks-offer");
  const firstSync = current.jira !== null && current.jira.last_synced_at === null;
  const offer = !offerDismissed && incoming.board_id === null && incoming.open > 0 && current.jira === null;
  return (
    <>
      <KanbanToolbar
        boards={boards}
        current={current}
        view={view}
        onViewChange={onViewChange}
        onAddTask={editable && columnOrder[0] ? () => cards.addCard(columnOrder[0]) : undefined}
      >
        <FieldsButton />
      </KanbanToolbar>
      <JiraErrorBanner board={current} />
      {offer ? <IncomingOffer board={current} open={incoming.open} onDismiss={dismissOffer} /> : null}
      {firstSync ? <FirstSync board={current} /> : <FilteredViews view={view} />}
    </>
  );
}

/** Строка фильтра и выбранный вид доски; если под фильтром ничего не нашлось — об этом и «Сбросить фильтры». */
function FilteredViews({ view }: { view: BoardView }) {
  const { shown, filtering } = useShownCount();
  if (filtering && shown === 0)
    return (
      <>
        <FilterBar />
        <NoMatches />
      </>
    );
  return (
    <>
      <FilterBar />
      {view === "board" ? (
        <KanbanBoard />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto bg-muted/25 p-4 lg:p-5">
          {view === "list" ? <TaskListView /> : <TaskTableView />}
        </div>
      )}
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
export function BoardScreen({ boards, current, incoming }: Omit<ViewProps, "view" | "onViewChange">) {
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

  // Новая версия с сервера (синхронизация закончилась, Jira прислала изменения) ложится в то же хранилище.
  return (
    <BoardProvider detail={detail.data}>
      <BoardBody boards={boards} current={current} incoming={incoming} view={view} onViewChange={setView} />
      <TaskPanel />
    </BoardProvider>
  );
}
