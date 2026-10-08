"use client";

import { Building2, CircleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useOpenSettings } from "@/features/settings/model/dialog-store";

import type { BoardSummary } from "../domain/board";
import { chooseWorkspaceTasksBoard } from "../model/board-actions";

/** When a Jira board's sync is paused: why, and where to fix it. The board stays readable meanwhile. */
export function JiraErrorBanner({ board }: { board: BoardSummary }) {
  const t = useTranslations("kanbanBoards");
  const openSettings = useOpenSettings();
  if (board.jira?.sync_status !== "error") return null;
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 border-b bg-destructive/5 px-4 py-2.5 text-sm lg:px-6"
    >
      <CircleAlert className="size-4 shrink-0 text-destructive" aria-hidden="true" />
      {/* Two sentences: the API's reason, worded in the request's language, then what that means here. */}
      <span className="min-w-0 flex-1">
        <span dir="auto">{board.jira.sync_error ?? t("banners.syncStopped")}</span>{" "}
        <span>{t("banners.changesPaused")}</span>
      </span>
      <Button size="sm" variant="outline" onClick={() => openSettings("connectors")}>
        {t("jira.openConnectors")}
      </Button>
    </div>
  );
}

/** The first sync of a Jira board, before its issues have arrived. */
export function FirstSync({ board }: { board: BoardSummary }) {
  const t = useTranslations("kanbanBoards");
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 bg-muted/25 p-6 text-center" role="status">
      <Spinner className="size-6 text-muted-foreground" />
      <p className="font-medium">{t("banners.importing", { board: board.jira?.board_name ?? board.name })}</p>
      <p className="max-w-sm text-muted-foreground text-sm">{t("banners.importingHint")}</p>
    </div>
  );
}

/**
 * Offers, once, to show the user's workspace tasks on this board. Nothing lands on a personal board
 * without being asked for; the choice can be changed in the board menu.
 */
export function WorkspaceTasksOffer({
  board,
  open,
  onDismiss,
}: {
  board: BoardSummary;
  open: number;
  onDismiss: () => void;
}) {
  const t = useTranslations("kanbanBoards");
  return (
    <div className="flex flex-wrap items-center gap-3 border-b bg-muted/40 px-4 py-2.5 text-sm lg:px-6">
      <Building2 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="min-w-0 flex-1">{t("banners.offer", { count: open, board: board.name })}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          {t("banners.notNow")}
        </Button>
        <Button size="sm" onClick={() => void chooseWorkspaceTasksBoard(board.id, board.name, t)}>
          {t("banners.showHere", { count: open })}
        </Button>
      </div>
    </div>
  );
}
