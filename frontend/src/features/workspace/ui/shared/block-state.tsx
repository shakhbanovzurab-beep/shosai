"use client";

import type { ReactNode } from "react";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

/** What a block shows, for its loading and error lines. */
export type BlockContent = "files" | "tasks" | "yourTasks" | "projects" | "meetings" | "upcomingMeetings" | "decisions";

/**
 * One block of a dashboard-like page: a skeleton while its data loads, a one-line retry if it fails
 * (the rest of the page keeps working), then the content.
 */
export function BlockState<T>({
  state,
  onRetry,
  what,
  height = "h-40",
  children,
}: {
  state: ResourceState<T>;
  onRetry: () => void;
  what: BlockContent;
  height?: string;
  children: (data: T) => ReactNode;
}) {
  const t = useTranslations("workspace");
  const common = useTranslations("common");
  if (state.status === "loading")
    return (
      <>
        <span className="sr-only">{t(`blocks.loading.${what}`)}</span>
        <Skeleton className={cn("rounded-xl", height)} />
      </>
    );
  if (state.status === "error")
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed px-4 py-4 text-sm">
        <span className="text-muted-foreground">{t(`blocks.failed.${what}`)}</span>
        <Button variant="outline" size="sm" onClick={onRetry}>
          {common("actions.retry")}
        </Button>
      </div>
    );
  return children(state.data);
}
