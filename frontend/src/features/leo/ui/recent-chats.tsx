"use client";

import { History } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { LeoThreads } from "../model/use-agent-threads";
import { RecentChatRow } from "./recent-chat-row";

/** «Недавние чаты» пространства в шапке панели: открыть, переименовать или удалить прежний разговор. */
export function RecentChats({ threads }: { readonly threads: LeoThreads }) {
  const t = useTranslations("leo");
  return (
    <Popover open={threads.open} onOpenChange={threads.setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={t("recent.title")} className="text-muted-foreground">
              <History />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent>{t("recent.title")}</TooltipContent>
      </Tooltip>
      <PopoverContent
        align="start"
        className="flex max-h-96 w-72 flex-col gap-1 overflow-y-auto p-1"
        onEscapeKeyDown={(event) => {
          // Escape в поле названия отменяет только правку, меню остаётся открытым.
          if (event.target instanceof HTMLInputElement) event.preventDefault();
        }}
        onKeyDown={(event) => {
          // События портала всплывают по дереву React до панели: Escape здесь закрывает меню, а не Leo.
          if (event.key === "Escape") event.stopPropagation();
        }}
      >
        <p className="px-2 pt-1.5 pb-1 font-medium text-muted-foreground text-xs">{t("recent.title")}</p>
        <RecentList threads={threads} />
      </PopoverContent>
    </Popover>
  );
}

function RecentList({ threads }: { readonly threads: LeoThreads }) {
  const t = useTranslations("leo");
  if (threads.loading) {
    return (
      <div className="flex flex-col gap-1.5 p-2" role="status" aria-label={t("panel.loading")}>
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-3/4" />
      </div>
    );
  }
  if (threads.failed) return <p className="px-2 py-3 text-destructive text-sm">{t("recent.failed")}</p>;
  if (threads.items.length === 0) return <p className="px-2 py-3 text-muted-foreground text-sm">{t("recent.empty")}</p>;
  return (
    <>
      <ul className="flex flex-col gap-0.5">
        {threads.items.map((thread) => (
          <RecentChatRow
            key={thread.id}
            thread={thread}
            current={thread.id === threads.current}
            onSelect={threads.select}
            onRename={threads.rename}
            onRemove={threads.remove}
          />
        ))}
      </ul>
      {threads.more.available ? (
        <Button variant="ghost" size="sm" disabled={threads.more.loading} onClick={threads.more.load}>
          {t("recent.more")}
        </Button>
      ) : null}
    </>
  );
}
