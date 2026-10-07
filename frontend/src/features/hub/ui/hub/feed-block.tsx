"use client";

import { useState } from "react";

import Link from "next/link";

import { cn } from "cn";
import { CornerDownRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import type { FeedFact, FeedMeeting } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import { momentLabel } from "../../domain/phrases";
import { loadEarlier, retry, useFeed } from "../../model/hooks";
import { Block, BlockError, PartialNote, QuietEmpty } from "../shared/block";
import { useHubPhrases } from "../shared/phrases";

function Fact({ fact, sessionId }: { fact: FeedFact; sessionId: string }) {
  const t = useTranslations("hubBlocks");
  const say = useHubPhrases();
  const replaced = fact.supersededBy;
  return (
    <li className="grid gap-x-3 gap-y-0.5 sm:grid-cols-[7.5rem_minmax(0,1fr)]">
      <span className="text-muted-foreground text-xs leading-5">{t(`feed.facts.${fact.kind}`)}</span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-pretty text-sm leading-5">
          <span dir="auto" className={cn(replaced && "text-muted-foreground line-through")}>
            {fact.text}
          </span>
          {replaced ? (
            <span className="ms-2 rounded-sm border px-1 align-middle text-[11px] text-muted-foreground no-underline">
              {t("feed.superseded")}
            </span>
          ) : null}
          {fact.startMs === null ? null : (
            <Link
              href={meetingPath(sessionId, fact.startMs)}
              className="ms-2 font-mono text-muted-foreground text-xs tabular-nums underline-offset-4 hover:text-foreground hover:underline"
              aria-label={t("feed.jumpTo", { moment: momentLabel(fact.startMs) })}
            >
              {momentLabel(fact.startMs)}
            </Link>
          )}
        </p>
        {replaced ? (
          <Link
            href={meetingPath(replaced.sessionId)}
            className="flex items-start gap-1 text-muted-foreground text-xs underline-offset-4 hover:text-foreground hover:underline"
          >
            <CornerDownRight className="mt-px size-3 shrink-0 rtl:-scale-x-100" aria-hidden="true" />
            {t("feed.replacedBy", { text: replaced.text, date: say.date(replaced.at) })}
          </Link>
        ) : null}
      </div>
    </li>
  );
}

function Meeting({ meeting }: { meeting: FeedMeeting }) {
  const t = useTranslations("hubBlocks");
  const say = useHubPhrases();
  return (
    <li className="flex flex-col gap-2 border-t pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <time dateTime={meeting.meetingStartedAt} className="text-muted-foreground text-xs tabular-nums">
          {say.date(meeting.meetingStartedAt)}
        </time>
        <Link
          href={meetingPath(meeting.sessionId)}
          dir="auto"
          className="font-medium text-sm underline-offset-4 hover:underline"
        >
          {meeting.meetingTitle}
        </Link>
      </div>
      {meeting.facts.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {meeting.facts.map((fact) => (
            <Fact key={fact.id} fact={fact} sessionId={meeting.sessionId} />
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-xs">{t("feed.quiet")}</p>
      )}
    </li>
  );
}

/** "What happened here": the hub's meetings and what was said in them, newest first, a page at a time. */
export function FeedBlock({ hubId }: { hubId: string }) {
  const t = useTranslations("hubBlocks");
  const state = useFeed(hubId);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreFailed, setMoreFailed] = useState(false);

  let body: React.ReactNode = (
    <div className="flex flex-col gap-5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/5" />
        </div>
      ))}
    </div>
  );
  if (state.status === "error")
    body = <BlockError title={t("feed.loadError")} onRetry={() => void retry.feed(hubId)} />;
  else if (state.status === "ready") {
    const { meetings, nextCursor } = state.data.data;
    body = (
      <>
        {state.data.partial ? <PartialNote onRetry={() => void retry.feed(hubId)} /> : null}
        {meetings.length === 0 ? (
          <QuietEmpty>{t("feed.empty")}</QuietEmpty>
        ) : (
          <ol className="flex flex-col gap-4">
            {meetings.map((meeting) => (
              <Meeting key={meeting.sessionId} meeting={meeting} />
            ))}
          </ol>
        )}
        {nextCursor ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              className="w-fit bg-background"
              disabled={loadingMore}
              onClick={async () => {
                setLoadingMore(true);
                setMoreFailed(!(await loadEarlier(hubId, nextCursor)));
                setLoadingMore(false);
              }}
            >
              {t("feed.earlier")}
            </Button>
            {moreFailed ? <span className="text-muted-foreground text-xs">{t("feed.loadError")}</span> : null}
          </div>
        ) : null}
      </>
    );
  }

  return (
    <Block id="feed" title={t("feed.title")}>
      {body}
    </Block>
  );
}
