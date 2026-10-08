"use client";

import { ArrowLeft, Kanban, TriangleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import type { Hub } from "../../domain/contract";
import { boardPath, HUBS_PATH } from "../../domain/paths";
import { restoreHub } from "../../model/hub-actions";
import { useHubWords } from "../../model/words";
import type { HubDialogKind } from "../dialogs/hub-dialogs";
import { HubMenu } from "../dialogs/hub-menu";
import { useHubPhrases } from "../shared/phrases";
import { WARNING_INK } from "../shared/urgency-tones";

/** Where the hub's work goes; without a board, a quiet warning ahead of time, not a refusal later. */
export function BoardLine({ hub, onChoose }: { hub: Hub; onChoose?: () => void }) {
  const t = useTranslations("hub");
  if (hub.boardId && hub.boardName)
    return (
      <span className="inline-flex min-w-0 items-center gap-1.5">
        <Kanban className="size-3.5 shrink-0" aria-hidden="true" />
        <Link
          href={boardPath(hub.boardId)}
          className="truncate underline-offset-4 hover:text-foreground hover:underline"
        >
          {t("list.boardTo", { board: hub.boardName })}
        </Link>
      </span>
    );
  return (
    <span className="inline-flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1">
      <TriangleAlert className={`size-3.5 shrink-0 ${WARNING_INK}`} aria-hidden="true" />
      <span>{t("list.noBoard")}</span>
      {onChoose ? (
        <Button variant="outline" size="xs" className="ms-1 bg-background" onClick={onChoose}>
          {t("list.chooseBoard")}
        </Button>
      ) : null}
    </span>
  );
}

/** The hub's name, where its work goes, how much happened in it, and its menu. */
export function HubHeader({ hub, onAction }: { hub: Hub; onAction: (kind: HubDialogKind, hub: Hub) => void }) {
  const t = useTranslations("hub");
  const words = useHubWords();
  const say = useHubPhrases();
  const facts = [
    t("page.meetings", { count: hub.meetingCount }),
    t("page.agreements", { count: hub.agreementCount }),
    hub.rhythmDays === null ? null : say.rhythm(hub.rhythmDays),
  ].filter(Boolean);
  return (
    <header className="flex flex-col gap-3">
      <Button variant="ghost" size="sm" className="-ms-2 w-fit bg-transparent text-muted-foreground" asChild>
        <Link href={HUBS_PATH}>
          <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
          {t("page.back")}
        </Link>
      </Button>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <h1 dir="auto" className="text-balance font-semibold text-2xl leading-tight tracking-tight">
            {hub.name}
          </h1>
          {hub.archived ? <Badge variant="secondary">{t("list.archived")}</Badge> : null}
        </div>
        <HubMenu hub={hub} onAction={onAction} className="shrink-0 border-border bg-background" />
      </div>
      <div className="flex flex-col gap-1 text-muted-foreground text-sm">
        <BoardLine hub={hub} onChoose={() => onAction("board", hub)} />
        <p>{facts.join(" · ")}</p>
      </div>
      {hub.archived ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed px-3 py-2 text-muted-foreground text-sm">
          <span>{t("page.archivedNote")}</span>
          <Button variant="outline" size="sm" className="bg-background" onClick={() => void restoreHub(words, hub)}>
            {t("list.restore")}
          </Button>
        </div>
      ) : null}
    </header>
  );
}
