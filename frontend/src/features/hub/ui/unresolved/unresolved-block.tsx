"use client";

import type { KeyboardEvent } from "react";

import { CircleCheck } from "lucide-react";
import { useTranslations } from "use-intl";

import { Skeleton } from "@/components/ui/skeleton";

import { unresolvedRows } from "../../domain/urgency";
import { retry, useHubThreads } from "../../model/hooks";
import { Block, BlockError, PartialNote, QuietEmpty } from "../shared/block";
import { UnresolvedRow } from "./unresolved-row";

/** Skeleton rows the size of real ones (subject, status, actions), so nothing jumps when they arrive. */
export function UnresolvedSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity.
        <div key={i} className="flex flex-col gap-2 py-3 ps-5">
          <Skeleton className="h-4 w-2/5" />
          <Skeleton className="h-4 w-3/5" />
          <Skeleton className="h-6 w-56" />
        </div>
      ))}
    </div>
  );
}

/** Arrow keys move between rows; Tab still walks through each row's actions. */
function moveBetweenRows(event: KeyboardEvent<HTMLOListElement>) {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const target = event.target as HTMLElement;
  if (!target.matches("[data-row-link]")) return;
  const links = [...event.currentTarget.querySelectorAll<HTMLElement>("[data-row-link]")];
  const next = links[links.indexOf(target) + (event.key === "ArrowDown" ? 1 : -1)];
  if (!next) return;
  event.preventDefault();
  next.focus();
}

/**
 * "What's unresolved": the main block of a hub. At most twelve rows, most urgent first (the server
 * finds what's missing; the order is the specification's). Nothing open is a calm, valid answer.
 */
export function UnresolvedBlock({ hubId, onOpen }: { hubId: string; onOpen: (threadId: string) => void }) {
  const t = useTranslations("hubBlocks");
  const state = useHubThreads(hubId);

  let body: React.ReactNode = <UnresolvedSkeleton />;
  if (state.status === "error")
    body = <BlockError title={t("unresolved.loadError")} onRetry={() => void retry.threads(hubId)} />;
  else if (state.status === "ready") {
    const rows = unresolvedRows(state.data.data);
    const hidden = state.data.data.length - rows.length;
    body = (
      <>
        {state.data.partial ? <PartialNote onRetry={() => void retry.threads(hubId)} /> : null}
        {rows.length === 0 && !state.data.partial ? (
          <QuietEmpty icon={<CircleCheck className="size-4 shrink-0" aria-hidden="true" />}>
            {t("unresolved.empty")}
          </QuietEmpty>
        ) : (
          <ol className="-mx-2 flex flex-col" onKeyDown={moveBetweenRows}>
            {rows.map((thread) => (
              <UnresolvedRow key={thread.id} thread={thread} onOpen={onOpen} />
            ))}
          </ol>
        )}
        {hidden > 0 ? <p className="text-muted-foreground text-xs">{t("unresolved.more", { count: hidden })}</p> : null}
      </>
    );
  }

  return (
    <Block id="unresolved" title={<span className="text-base text-foreground">{t("unresolved.title")}</span>}>
      {body}
    </Block>
  );
}
