"use client";

import Link from "next/link";

import { Sun } from "lucide-react";
import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";

import type { BriefItem } from "../../domain/contract";
import { hubPath, threadPath } from "../../domain/paths";
import { retry, useBrief } from "../../model/hooks";
import { Block, BlockError, PartialNote, QuietEmpty } from "../shared/block";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";

/** Items of the brief grouped by hub, in the server's order. */
function byHub(items: BriefItem[]) {
  const groups = new Map<string, { name: string; items: BriefItem[] }>();
  for (const item of items) {
    const group = groups.get(item.hub.id) ?? { name: item.hub.name, items: [] };
    group.items.push(item);
    groups.set(item.hub.id, group);
  }
  return [...groups.entries()];
}

/**
 * "Today", across hubs: only what is really on fire, a few lines per hub. An empty brief is the
 * normal good outcome and reads as one calm line.
 */
export function TodayBrief() {
  const t = useTranslations("hubMeetings");
  const api = useTranslations("hubApi");
  const say = useHubPhrases();
  const state = useBrief();
  let body: React.ReactNode = (
    <div className="flex flex-col gap-2" aria-hidden="true">
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
  if (state.status === "error") body = <BlockError title={api("errors.unknown")} onRetry={() => void retry.brief()} />;
  else if (state.status === "ready")
    body = (
      <>
        {state.data.partial ? <PartialNote onRetry={() => void retry.brief()} /> : null}
        {state.data.data.items.length === 0 ? (
          <QuietEmpty icon={<Sun className="size-4 shrink-0" aria-hidden="true" />}>{t("brief.empty")}</QuietEmpty>
        ) : (
          <div className="flex flex-col gap-4">
            {byHub(state.data.data.items).map(([hubId, group]) => (
              <div key={hubId} className="flex flex-col gap-1.5">
                <Link
                  href={hubPath(hubId)}
                  dir="auto"
                  className="w-fit font-medium text-sm underline-offset-4 hover:underline"
                >
                  {group.name}
                </Link>
                <ul className="flex flex-col gap-1.5">
                  {group.items.map(({ thread }) => (
                    <li key={thread.id} className="flex items-start gap-2 text-sm">
                      {thread.gap ? <GapIcon kind={thread.gap.kind} className="mt-0.5" /> : null}
                      <span className="min-w-0">
                        <Link
                          href={threadPath(hubId, thread.id)}
                          dir="auto"
                          className="underline decoration-border underline-offset-4 hover:decoration-foreground"
                        >
                          {thread.subject}
                        </Link>
                        {thread.gap ? <span className="text-muted-foreground"> — {say.gap(thread.gap)}</span> : null}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </>
    );
  return (
    <Block id="brief-today" title={t("brief.title")}>
      {body}
    </Block>
  );
}
