"use client";

import { useTranslations } from "use-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/lib/navigation";

import type { ThreadSummary } from "../../domain/contract-threads";
import { meetingPath, threadPath } from "../../domain/paths";
import { retry, useDigest } from "../../model/hooks";
import { Block, BlockError, PartialNote } from "../shared/block";
import { useHubPhrases } from "../shared/phrases";

function Group({
  label,
  hint,
  threads,
  onOpen,
}: {
  label: string;
  hint?: string;
  threads: ThreadSummary[];
  onOpen: (threadId: string) => void;
}) {
  if (threads.length === 0) return null;
  return (
    <div className="grid gap-x-6 gap-y-1 sm:grid-cols-[8rem_minmax(0,1fr)]">
      <dt className="text-muted-foreground text-sm">{label}</dt>
      <dd className="flex min-w-0 flex-col gap-1">
        <ul className="flex flex-col gap-1">
          {threads.map((thread) => (
            <li key={thread.id}>
              <Link
                href={threadPath(thread.hubId, thread.id)}
                scroll={false}
                dir="auto"
                className="text-sm underline decoration-border underline-offset-4 hover:decoration-foreground"
                onClick={(event) => {
                  if (event.metaKey || event.ctrlKey || event.shiftKey) return;
                  event.preventDefault();
                  onOpen(thread.id);
                }}
              >
                {thread.subject}
              </Link>
            </li>
          ))}
        </ul>
        {hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
      </dd>
    </div>
  );
}

/**
 * "Since the last meeting": the difference, not a retelling. The third group is the main one: what
 * holds the hub up and wasn't mentioned. Empty groups are left out; with all three empty, so is the block.
 */
export function DigestBlock({ hubId, onOpen }: { hubId: string; onOpen: (threadId: string) => void }) {
  const t = useTranslations("hubBlocks");
  const say = useHubPhrases();
  const state = useDigest(hubId);
  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-3" aria-hidden="true">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  if (state.status === "error")
    return (
      <Block id="digest" title={t("digest.title")}>
        <BlockError title={t("digest.loadError")} onRetry={() => void retry.digest(hubId)} />
      </Block>
    );
  const digest = state.data.data;
  const empty = !digest || digest.opened.length + digest.closed.length + digest.untouched.length === 0;
  if (empty && !state.data.partial) return null;
  return (
    <Block
      id="digest"
      title={t("digest.title")}
      aside={
        digest ? (
          <Link
            href={meetingPath(digest.sessionId)}
            className="text-muted-foreground text-xs underline-offset-4 hover:text-foreground hover:underline"
          >
            {t("digest.meeting", { title: digest.meetingTitle, date: say.date(digest.meetingStartedAt) })}
          </Link>
        ) : null
      }
    >
      {state.data.partial ? <PartialNote onRetry={() => void retry.digest(hubId)} /> : null}
      {digest ? (
        <dl className="flex flex-col gap-3">
          <Group label={t("digest.opened")} threads={digest.opened} onOpen={onOpen} />
          <Group label={t("digest.closed")} threads={digest.closed} onOpen={onOpen} />
          <Group
            label={t("digest.untouched")}
            hint={t("digest.untouchedHint")}
            threads={digest.untouched}
            onOpen={onOpen}
          />
        </dl>
      ) : null}
    </Block>
  );
}
