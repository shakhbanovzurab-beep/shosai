"use client";

import { useState, useTransition } from "react";

import { cn } from "cn";
import { ArrowLeftRight, Plug } from "lucide-react";
import { siJira } from "simple-icons";
import { useTranslations } from "use-intl";

import { SimpleIcon } from "@/components/simple-icon";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useOpenSettings } from "@/features/settings/model/dialog-store";
import { Link, useRouter } from "@/lib/navigation";

import { boardHref } from "../domain/board";
import type { JiraBoard } from "../domain/boards-contract";
import { connectJiraBoard } from "../model/board-actions";
import { useJiraBoards } from "../model/boards-resource";

const HOW_IT_SYNCS = ["howColumns", "howMoves", "howChanges"] as const;

/** A Jira board's facts in one row; each is its own item, so they keep their order right to left too. */
function BoardFacts({ board }: { board: JiraBoard }) {
  const t = useTranslations("kanbanBoards");
  const facts = {
    key: board.project_key,
    project: board.project_name,
    type: t(`jira.type.${board.type}`),
    site: board.site,
  };
  return (
    <span className="flex flex-wrap gap-x-1 text-muted-foreground text-xs">
      {Object.entries(facts).map(([id, fact], index) => (
        <span key={id} className="flex gap-x-1">
          {index > 0 ? <span aria-hidden="true">·</span> : null}
          <span dir="auto">{fact}</span>
        </span>
      ))}
    </span>
  );
}

function JiraPicker({ onDone }: { onDone: () => void }) {
  const t = useTranslations("kanbanBoards");
  const ta = useTranslations("kanbanApi");
  const tc = useTranslations("common");
  const router = useRouter();
  const openSettings = useOpenSettings();
  const state = useJiraBoards();
  const [selected, setSelected] = useState<JiraBoard | null>(null);
  const [pending, startTransition] = useTransition();

  if (state.status === "loading") return <Spinner className="mx-auto my-10 size-6 text-muted-foreground" />;
  if (state.status === "error") return <p className="py-6 text-center text-destructive text-sm">{state.message}</p>;

  if (!state.data.connected)
    return (
      <Empty className="py-6">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Plug />
          </EmptyMedia>
          <EmptyTitle>{t("jira.connectTitle")}</EmptyTitle>
          <EmptyDescription>{t("jira.connectDescription")}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button
            onClick={() => {
              onDone();
              openSettings("connectors");
            }}
          >
            {t("jira.openConnectors")}
          </Button>
        </EmptyContent>
      </Empty>
    );

  const sync = (board: JiraBoard) =>
    startTransition(async () => {
      const created = await connectJiraBoard({ site: board.site, board_id: board.board_id }, { t, ta });
      if (!created) return;
      onDone();
      router.push(boardHref(created.id));
    });

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        {state.data.account ? t("jira.connectedAs", { account: state.data.account }) : t("jira.connected")}
      </p>
      {state.data.items.length === 0 ? (
        <p className="rounded-lg border border-dashed px-4 py-6 text-center text-muted-foreground text-sm">
          {t("jira.noBoards")}
        </p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label={t("jira.boardList")}>
          {state.data.items.map((board) => (
            <li key={`${board.site}/${board.board_id}`}>
              {board.synced_board_id ? (
                <Link
                  href={boardHref(board.synced_board_id)}
                  onClick={onDone}
                  className="flex items-center justify-between gap-3 rounded-lg border bg-muted/40 p-3 text-sm"
                >
                  <span className="flex flex-col">
                    <span dir="auto" className="font-medium">
                      {board.name}
                    </span>
                    <span className="text-muted-foreground text-xs">{t("jira.alreadySynced")}</span>
                  </span>
                </Link>
              ) : (
                <button
                  type="button"
                  aria-pressed={selected?.board_id === board.board_id}
                  onClick={() => setSelected(board)}
                  className={cn(
                    "flex w-full cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-start text-sm outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
                    selected?.board_id === board.board_id ? "border-primary bg-primary/5" : "hover:bg-muted",
                  )}
                >
                  <span dir="auto" className="font-medium">
                    {board.name}
                  </span>
                  <BoardFacts board={board} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ul className="flex flex-col gap-1.5 rounded-lg bg-muted/40 p-3 text-muted-foreground text-xs">
        {HOW_IT_SYNCS.map((line) => (
          <li key={line} className="flex gap-2">
            <ArrowLeftRight className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
            {t(`jira.${line}`)}
          </li>
        ))}
      </ul>
      <DialogFooter>
        <Button variant="ghost" onClick={onDone}>
          {tc("actions.cancel")}
        </Button>
        <Button disabled={!selected || pending} onClick={() => (selected ? sync(selected) : undefined)}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("jira.sync")}
        </Button>
      </DialogFooter>
    </div>
  );
}

/** Picks a Jira board to sync two-way with a board here. */
export function JiraBoardDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const t = useTranslations("kanbanBoards");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <SimpleIcon icon={siJira} aria-hidden="true" className="size-4 fill-blue-600 dark:fill-blue-400" />
            {t("jira.title")}
          </DialogTitle>
          <DialogDescription>{t("jira.description")}</DialogDescription>
        </DialogHeader>
        {open ? <JiraPicker onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
