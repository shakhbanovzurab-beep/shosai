"use client";

import { Building2, CircleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useOpenSettings } from "@/features/settings/model/dialog-store";

import type { BoardSummary } from "../domain/boards-contract";
import { KANBAN_PROBLEMS } from "../domain/problems";
import { chooseIncomingBoard } from "../model/board-actions";

/** When a Jira board's sync is paused: why, and where to fix it. The board stays readable meanwhile. */
export function JiraErrorBanner({ board }: { board: BoardSummary }) {
  const t = useTranslations("kanbanBoards");
  const ta = useTranslations("kanbanApi");
  const openSettings = useOpenSettings();
  if (board.jira?.sync_status !== "error") return null;
  const reason = KANBAN_PROBLEMS.find((code) => code === board.jira?.sync_error);
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 border-b bg-destructive/5 px-4 py-2.5 text-sm lg:px-6"
    >
      <CircleAlert className="size-4 shrink-0 text-destructive" aria-hidden="true" />
      {/* Два предложения: причина по коду API словами кабинета, затем что это значит здесь. */}
      <span className="min-w-0 flex-1">
        <span>{reason ? ta(reason) : t("banners.syncStopped")}</span> <span>{t("banners.changesPaused")}</span>
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
 * Один раз предлагает класть сюда задачи, которые приходят к человеку (TK-D4). Без спроса на личную доску
 * ничего не ложится; выбор меняется в меню доски.
 */
export function IncomingOffer({
  board,
  open,
  onDismiss,
}: {
  board: BoardSummary;
  open: number;
  onDismiss: () => void;
}) {
  const t = useTranslations("kanbanBoards");
  const ta = useTranslations("kanbanApi");
  return (
    <div className="flex flex-wrap items-center gap-3 border-b bg-muted/40 px-4 py-2.5 text-sm lg:px-6">
      <Building2 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="min-w-0 flex-1">{t("banners.offer", { count: open, board: board.name })}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          {t("banners.notNow")}
        </Button>
        <Button size="sm" onClick={() => void chooseIncomingBoard(board.id, board.name, { t, ta })}>
          {t("banners.showHere", { count: open })}
        </Button>
      </div>
    </div>
  );
}
