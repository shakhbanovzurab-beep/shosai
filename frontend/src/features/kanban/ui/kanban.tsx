"use client";

import { useState } from "react";

import { Kanban as KanbanIcon, Plus } from "lucide-react";
import { siJira } from "simple-icons";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { SimpleIcon } from "@/components/simple-icon";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

import { boardsResource, useBoards } from "../model/boards-resource";
import { BoardScreen } from "./board-screen";
import { JiraBoardDialog } from "./jira-board-dialog";
import { NewBoardDialog } from "./new-board-dialog";

function NoBoards() {
  const t = useTranslations("kanbanBoards");
  const [dialog, setDialog] = useState<"new" | "jira" | null>(null);
  return (
    <Empty className="m-auto">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <KanbanIcon />
        </EmptyMedia>
        <EmptyTitle>{t("empty.title")}</EmptyTitle>
        <EmptyDescription>{t("empty.description")}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="flex-row justify-center gap-2">
        <Button onClick={() => setDialog("new")}>
          <Plus data-icon="inline-start" />
          {t("empty.newBoard")}
        </Button>
        <Button variant="outline" onClick={() => setDialog("jira")}>
          <SimpleIcon icon={siJira} aria-hidden="true" className="size-4 fill-current" />
          {t("empty.syncJiraBoard")}
        </Button>
      </EmptyContent>
      <NewBoardDialog open={dialog === "new"} onOpenChange={(open) => setDialog(open ? "new" : null)} />
      <JiraBoardDialog open={dialog === "jira"} onOpenChange={(open) => setDialog(open ? "jira" : null)} />
    </Empty>
  );
}

function KanbanScreen({ boardId }: { boardId: string | null }) {
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const state = useBoards();
  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-4 p-4 lg:p-6">
        <span className="sr-only">{tc("feedback.loading")}</span>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    );
  if (state.status === "error")
    return (
      <div className="p-6">
        <LoadError
          title={t("loadBoardsFailed")}
          message={state.message}
          retryLabel={tc("actions.retry")}
          onRetry={() => void boardsResource.refresh()}
        />
      </div>
    );

  const { items: boards, incoming } = state.data;
  // An unknown or deleted board falls back to the first one.
  const current = boards.find((b) => b.id === boardId) ?? boards[0];
  if (!current) return <NoBoards />;
  return <BoardScreen key={current.id} boards={boards} current={current} incoming={incoming} />;
}

/** The full-bleed Kanban screen: the board picked in `?board=`, or the first board. */
export function Kanban({ boardId }: { boardId: string | null }) {
  return (
    <div data-content-padding="false">
      <div className="flex h-[calc(100dvh-var(--dashboard-header-height))] min-h-0 min-w-0 flex-col overflow-hidden">
        <KanbanScreen boardId={boardId} />
      </div>
    </div>
  );
}
