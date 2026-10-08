"use client";

import { Check, CircleSlash } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import type { ThreadSummary } from "../../domain/contract-threads";
import { threadPath } from "../../domain/paths";
import { dismissedBefore } from "../../domain/phrases";
import { showCircles } from "../../domain/urgency";
import { preloadThread } from "../../model/hooks";
import { dismissGap, markDone } from "../../model/thread-actions";
import { useHubWords } from "../../model/words";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon, UrgencyBar } from "../shared/urgency";
import { ThreadWhy } from "../why/why-popover";
import { AssignPopover } from "./assign-popover";
import { CirclesBadge } from "./circles-badge";
import { rowAnchorId } from "./row-anchor";

/** Plain actions with an explicit frame and background, so a browser default never shows through. */
const ACTION = "relative z-10 border-transparent bg-transparent text-muted-foreground hover:text-foreground";

/**
 * Hidden only where hovering exists, shown on hover or keyboard focus there; always shown on touch.
 * An open popover keeps them visible.
 */
const ACTIONS_VISIBILITY =
  "[@media(hover:hover)]:opacity-0 group-hover/row:opacity-100 group-focus-within/row:opacity-100 group-has-[[data-state=open]]/row:opacity-100 motion-safe:transition-opacity";

/**
 * One row of "What's unresolved": the subject, the stage and what is missing in one phrase, and
 * actions beside it that can be ignored. The subject opens the details; the rest of the row too.
 */
export function UnresolvedRow({ thread, onOpen }: { thread: ThreadSummary; onOpen: (threadId: string) => void }) {
  const t = useTranslations("hubBlocks");
  const hubWords = useTranslations("hub");
  const words = useHubWords();
  const say = useHubPhrases();
  return (
    <li className="group/row relative rounded-lg py-3 ps-5 pe-2 hover:bg-muted/40 has-[a:focus-visible]:bg-muted/40">
      <UrgencyBar gap={thread.gap} />
      <div className="flex items-start justify-between gap-3">
        <a
          id={rowAnchorId(thread.id)}
          href={threadPath(thread.hubId, thread.id)}
          data-row-link=""
          aria-label={t("unresolved.rowLabel", { subject: thread.subject })}
          dir="auto"
          className="min-w-0 text-pretty font-medium text-sm leading-snug outline-none after:absolute after:inset-0 after:rounded-lg after:content-[''] focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
          onClick={(event) => {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
            event.preventDefault();
            onOpen(thread.id);
          }}
          onPointerEnter={() => preloadThread(thread.id)}
          onFocus={() => preloadThread(thread.id)}
        >
          {thread.subject}
        </a>
        {showCircles(thread.circles) ? <CirclesBadge threadId={thread.id} circles={thread.circles} /> : null}
      </div>
      <p className="mt-1 flex items-start gap-1.5 text-muted-foreground text-sm leading-snug">
        {thread.gap ? <GapIcon kind={thread.gap.kind} className="mt-0.5" /> : null}
        <span>{say.status(thread)}</span>
      </p>
      {dismissedBefore(thread) ? (
        <p className="mt-0.5 text-muted-foreground text-xs italic">{hubWords("dismissedBefore")}</p>
      ) : null}
      <div className={`-ms-2 mt-1.5 flex flex-wrap items-center gap-0.5 ${ACTIONS_VISIBILITY}`}>
        <ThreadWhy threadId={thread.id} />
        <Button variant="ghost" size="xs" className={ACTION} onClick={() => void markDone(words, thread)}>
          <Check data-icon="inline-start" aria-hidden="true" />
          {t("unresolved.done")}
        </Button>
        {thread.gap ? (
          <Button variant="ghost" size="xs" className={ACTION} onClick={() => void dismissGap(words, thread)}>
            <CircleSlash data-icon="inline-start" aria-hidden="true" />
            {t("unresolved.dismiss")}
          </Button>
        ) : null}
        {thread.owner === null ? <AssignPopover thread={thread} className={ACTION} /> : null}
      </div>
    </li>
  );
}
