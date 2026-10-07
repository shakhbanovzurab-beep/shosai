"use client";

import { useState } from "react";

import dynamic from "next/dynamic";

import { SearchX } from "lucide-react";
import { useTranslations } from "next-intl";

import { useDirection } from "@/components/ui/direction";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

import { retry, useThreadDetail } from "../../model/hooks";
import { BlockError } from "../shared/block";
import { rowAnchorId } from "../unresolved/row-anchor";

// The history, decisions and sources load with the panel, not with the hub page.
const ThreadView = dynamic(() => import("./thread-view").then((m) => m.ThreadView), {
  loading: () => <BodySkeleton />,
});

function BodySkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden="true">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

function Body({ threadId, onOpen }: { threadId: string; onOpen: (threadId: string) => void }) {
  const t = useTranslations("hubDetail");
  const common = useTranslations("common");
  const state = useThreadDetail(threadId);
  if (state.status === "loading")
    return (
      <>
        <SheetHeader className="p-0">
          <Skeleton className="h-6 w-1/2" />
          <SheetTitle className="sr-only">{common("feedback.loading")}</SheetTitle>
          <SheetDescription className="sr-only">{t("thread.panelLabel")}</SheetDescription>
        </SheetHeader>
        <BodySkeleton />
      </>
    );
  if (state.status === "error") {
    const gone = state.message === "not_found";
    return (
      <>
        <SheetHeader className="p-0">
          <SheetTitle>{gone ? t("thread.goneTitle") : t("thread.loadError")}</SheetTitle>
          <SheetDescription>{gone ? t("thread.goneText") : t("thread.panelLabel")}</SheetDescription>
        </SheetHeader>
        {gone ? (
          <SearchX className="size-6 text-muted-foreground" aria-hidden="true" />
        ) : (
          <BlockError title={t("thread.loadError")} onRetry={() => void retry.thread(threadId)} />
        )}
      </>
    );
  }
  return (
    <>
      <SheetHeader className="p-0 pe-8">
        <SheetTitle dir="auto" className="text-pretty font-semibold text-lg leading-snug">
          {state.data.subject}
        </SheetTitle>
        <SheetDescription className="sr-only">{t("thread.panelLabel")}</SheetDescription>
      </SheetHeader>
      <ThreadView detail={state.data} onOpen={onOpen} />
    </>
  );
}

/**
 * A topic over its hub's page: a side panel on a desktop, the whole screen on a phone; both have
 * the address `?open=<id>`. Esc closes it and puts focus back on its row.
 */
export function ThreadSheet({
  threadId,
  onClose,
  onOpen,
}: {
  threadId: string | null;
  onClose: () => void;
  onOpen: (threadId: string) => void;
}) {
  // The last one opened stays rendered while the panel slides out, and is where focus returns.
  const [shown, setShown] = useState(threadId);
  // The panel comes in from the end of the line: the right in left-to-right languages, the left in Arabic.
  const side = useDirection() === "rtl" ? "left" : "right";
  if (threadId !== null && threadId !== shown) setShown(threadId);
  return (
    <Sheet open={threadId !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent
        side={side}
        className="w-full gap-0 overflow-y-auto p-5 data-[side=left]:w-full data-[side=right]:w-full sm:p-6 data-[side=left]:sm:max-w-xl data-[side=right]:sm:max-w-xl"
        onCloseAutoFocus={(event) => {
          const row = shown ? document.getElementById(rowAnchorId(shown)) : null;
          if (!row) return;
          event.preventDefault();
          row.focus();
        }}
      >
        <div className="flex flex-col gap-6">{shown ? <Body threadId={shown} onOpen={onOpen} /> : null}</div>
      </SheetContent>
    </Sheet>
  );
}
