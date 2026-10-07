"use client";

import { Check, CircleSlash, Repeat, Slash } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import type { ThreadDetail } from "../../domain/contract";
import { circlesHint } from "../../domain/phrases";
import { isOpenStage, showCircles } from "../../domain/urgency";
import { dismissGap, markAbandoned, markDone } from "../../model/thread-actions";
import { useHubWords } from "../../model/words";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";
import { AssignPopover } from "../unresolved/assign-popover";
import { DecisionSection } from "./decision";
import { History } from "./history";
import { StageTrack } from "./stage-track";
import { Dismissals, Links, Sources } from "./thread-extras";

function Meta({ detail }: { detail: ThreadDetail }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  return (
    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
      <dt className="text-muted-foreground">{t("thread.owner")}</dt>
      <dd dir={detail.owner ? "auto" : undefined}>
        {detail.owner ?? <span className="text-muted-foreground">{t("thread.noOwner")}</span>}
      </dd>
      <dt className="text-muted-foreground">{t("thread.due")}</dt>
      <dd>
        {detail.dueAt ? say.date(detail.dueAt) : <span className="text-muted-foreground">{t("thread.noDue")}</span>}
      </dd>
    </dl>
  );
}

/** The same actions as the row, plus "Abandoned" for closing it without doing it. */
function Actions({ detail }: { detail: ThreadDetail }) {
  const t = useTranslations("hubBlocks");
  const words = useHubWords();
  if (!isOpenStage(detail.stage)) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      <Button variant="outline" size="sm" className="bg-background" onClick={() => void markDone(words, detail)}>
        <Check data-icon="inline-start" aria-hidden="true" />
        {t("unresolved.done")}
      </Button>
      {detail.gap ? (
        <Button variant="outline" size="sm" className="bg-background" onClick={() => void dismissGap(words, detail)}>
          <CircleSlash data-icon="inline-start" aria-hidden="true" />
          {t("unresolved.dismiss")}
        </Button>
      ) : null}
      {detail.owner === null ? <AssignPopover thread={detail} className="h-7 border-border bg-background" /> : null}
      <Button variant="outline" size="sm" className="bg-background" onClick={() => void markAbandoned(words, detail)}>
        <Slash data-icon="inline-start" aria-hidden="true" />
        {t("unresolved.abandon")}
      </Button>
    </div>
  );
}

/**
 * A topic with its history: where it stands, every round with what stood in the way, the decision
 * and how it turned out, what it is linked to, and every source.
 */
export function ThreadView({ detail, onOpen }: { detail: ThreadDetail; onOpen: (threadId: string) => void }) {
  const t = useTranslations("hub");
  const say = useHubPhrases();
  const hint = showCircles(detail.circles) ? circlesHint(detail) : null;
  return (
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-3">
        <p className="flex items-start gap-1.5 text-muted-foreground text-sm">
          {detail.gap ? <GapIcon kind={detail.gap.kind} className="mt-0.5" /> : null}
          {say.status(detail)}
        </p>
        {hint ? (
          <p className="flex items-center gap-1.5 text-muted-foreground text-xs">
            <Repeat className="size-3" aria-hidden="true" />
            {t("circles", { count: detail.circles })} —{" "}
            {t("circlesHint", { count: hint.length, dates: say.dates(hint) })}
          </p>
        ) : null}
        <Meta detail={detail} />
        <Actions detail={detail} />
      </div>
      <StageTrack stage={detail.stage} transitions={detail.transitions} />
      <DecisionSection detail={detail} />
      <History detail={detail} />
      <Links detail={detail} onOpen={onOpen} />
      <Dismissals detail={detail} />
      <Sources detail={detail} />
    </div>
  );
}
