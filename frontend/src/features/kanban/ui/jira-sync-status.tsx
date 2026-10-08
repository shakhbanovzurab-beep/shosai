"use client";

import { useTransition } from "react";

import { CircleAlert, ExternalLink, RefreshCw } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { BoardSummary, JiraLink } from "../domain/board";
import { syncBoard } from "../model/board-actions";

/** "Synced with Jira 5 minutes ago", brought up to date once a minute while the board is open. */
function SyncedAgo({ at }: { at: string }) {
  const t = useTranslations("kanbanBoards");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  // A sync newer than the last tick reads "now", never "in 20 seconds".
  const synced = new Date(Math.min(Date.parse(at), now.getTime()));
  return t("sync.syncedAgo", { ago: format.relativeTime(synced, now) });
}

function Status({ jira }: { jira: JiraLink }) {
  const t = useTranslations("kanbanBoards");
  if (jira.sync_status === "syncing")
    return (
      <span className="flex items-center gap-1.5">
        <Spinner className="size-3.5" />
        {t("sync.syncing")}
      </span>
    );
  if (jira.sync_status === "error")
    return (
      <span className="flex items-center gap-1.5 text-destructive">
        <CircleAlert className="size-3.5" aria-hidden="true" />
        {t("sync.paused")}
      </span>
    );
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
      {jira.last_synced_at ? <SyncedAgo at={jira.last_synced_at} /> : t("sync.synced")}
    </span>
  );
}

/** Where a synced board stands with Jira, with "Sync now" and a link to the board in Jira. */
export function JiraSyncStatus({ board }: { board: BoardSummary }) {
  const t = useTranslations("kanbanBoards");
  const [pending, startTransition] = useTransition();
  const { jira } = board;
  if (!jira) return null;
  const busy = pending || jira.sync_status === "syncing";

  return (
    <div className="flex min-w-0 items-center gap-1 text-muted-foreground text-sm" role="status">
      <Status jira={jira} />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("sync.syncNow")}
            disabled={busy}
            onClick={() => startTransition(() => syncBoard(board.id, t))}
          >
            <RefreshCw className={busy ? "motion-safe:animate-spin" : undefined} />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("sync.syncNow")}</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button asChild variant="ghost" size="icon-sm">
            <a
              href={jira.board_url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t("sync.openBoard", { board: jira.board_name })}
            >
              <ExternalLink className="rtl:-scale-x-100" />
            </a>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("sync.openHint", { project: jira.project_key, site: jira.site })}</TooltipContent>
      </Tooltip>
    </div>
  );
}
