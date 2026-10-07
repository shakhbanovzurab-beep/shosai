"use client";

import { useState } from "react";

import { Repeat } from "lucide-react";
import { useTranslations } from "next-intl";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";

import { circlesHint } from "../../domain/phrases";
import { preloadThread, useThreadDetail } from "../../model/hooks";
import { useHubPhrases } from "../shared/phrases";

function Hint({ threadId }: { threadId: string }) {
  const t = useTranslations("hub");
  const detailWords = useTranslations("hubDetail");
  const common = useTranslations("common");
  const say = useHubPhrases();
  const detail = useThreadDetail(threadId);
  if (detail.status === "loading") return <Skeleton className="h-4 w-48" aria-label={common("feedback.loading")} />;
  if (detail.status === "error")
    return <span className="text-muted-foreground">{detailWords("thread.loadError")}</span>;
  const dates = circlesHint(detail.data);
  return dates ? <span>{t("circlesHint", { count: dates.length, dates: say.dates(dates) })}</span> : null;
}

/**
 * "round 3": the topic came back at three meetings and didn't move. The meeting dates show on hover
 * or on tap; the server counts the rounds, the badge only says the number.
 */
export function CirclesBadge({ threadId, circles }: { threadId: string; circles: number }) {
  const t = useTranslations("hub");
  const [open, setOpen] = useState(false);
  const hover = (next: boolean) => (event: React.PointerEvent) => {
    if (event.pointerType !== "mouse") return;
    if (next) preloadThread(threadId);
    setOpen(next);
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="relative z-10 inline-flex h-6 shrink-0 items-center gap-1 rounded-full border border-border bg-background px-2 text-muted-foreground text-xs tabular-nums outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
        onPointerEnter={hover(true)}
        onPointerLeave={hover(false)}
        onFocus={() => preloadThread(threadId)}
      >
        <Repeat className="size-3" aria-hidden="true" />
        <span key={circles} className="motion-safe:fade-in-0 motion-safe:zoom-in-90 motion-safe:animate-in">
          {t("circles", { count: circles })}
        </span>
      </PopoverTrigger>
      <PopoverContent side="top" align="end" className="w-auto max-w-[min(20rem,calc(100vw-2rem))] p-2.5 text-xs">
        <Hint threadId={threadId} />
      </PopoverContent>
    </Popover>
  );
}
