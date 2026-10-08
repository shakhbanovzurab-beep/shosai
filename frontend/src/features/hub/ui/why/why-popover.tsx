"use client";

import type { ReactNode } from "react";

import { CircleHelp } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";

import { whyEvidence } from "../../domain/phrases";
import { preloadThread, retry, useThreadDetail } from "../../model/hooks";
import { SourceCard } from "./source-card";

/** The source behind a row, loaded when asked for (or a moment earlier, on hover or focus). */
function ThreadSource({ threadId }: { threadId: string }) {
  const t = useTranslations("hubDetail");
  const common = useTranslations("common");
  const detail = useThreadDetail(threadId);
  if (detail.status === "loading")
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <span className="sr-only">{common("feedback.loading")}</span>
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  if (detail.status === "error")
    return (
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">{t("why.loadError")}</span>
        <Button variant="outline" size="xs" onClick={() => void retry.thread(threadId)}>
          {common("actions.retry")}
        </Button>
      </div>
    );
  const evidence = whyEvidence(detail.data);
  return evidence ? <SourceCard evidence={evidence} /> : null;
}

/** "Why?": a small, plain button that opens the explanation next to it. */
export function WhyButton({
  label,
  children,
  onIntent,
}: {
  label: string;
  children: ReactNode;
  onIntent?: () => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="xs"
          className="relative z-10 border-transparent bg-transparent text-muted-foreground hover:text-foreground"
          onPointerEnter={onIntent}
          onFocus={onIntent}
        >
          <CircleHelp data-icon="inline-start" aria-hidden="true" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(22rem,calc(100vw-2rem))] p-3.5">
        {children}
      </PopoverContent>
    </Popover>
  );
}

export function ThreadWhy({ threadId }: { threadId: string }) {
  const t = useTranslations("hubBlocks");
  return (
    <WhyButton label={t("unresolved.why")} onIntent={() => preloadThread(threadId)}>
      <ThreadSource threadId={threadId} />
    </WhyButton>
  );
}
