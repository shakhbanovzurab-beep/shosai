"use client";

import { Archive, Check, PenLine } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

import { isWaitingOnYou, type LeoMailView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { mailActions } from "../model/mail-store";
import { LeoTriageMenu } from "./leo-triage-menu";
import { reviewDraft } from "./review-draft";
import { useMailDates } from "./use-mail-dates";
import { useMailWords } from "./use-mail-words";

type LeoInsightCardProps = {
  mail: Mail;
  view: LeoMailView;
};

/** Leo's reading of the open email: what to do next, what it says, and the facts worth knowing. */
export function LeoInsightCard({ mail, view }: LeoInsightCardProps) {
  const t = useTranslations("mailLeo.card");
  const { insight } = view;
  const isWaiting = isWaitingOnYou(mail, view);

  return (
    <Card size="sm" className="shrink-0" role="region" aria-label={t("label")}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ThinkingOrb state="breathing" size={20} aria-hidden="true" />
          Leo
          {isWaiting ? <ReplyByBadge replyBy={insight.reply_by} /> : null}
        </CardTitle>
        <CardAction>
          <LeoTriageMenu mailId={mail.id} view={view} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {isWaiting && insight.next_step ? (
          <p dir="auto" className="font-medium">
            {insight.next_step}
          </p>
        ) : null}
        <p dir="auto" className="text-muted-foreground">
          {insight.summary}
        </p>
        <KeyPoints points={insight.key_points} />
      </CardContent>
      <InsightFooter mail={mail} view={view} />
    </Card>
  );
}

function ReplyByBadge({ replyBy }: { replyBy: string | null }) {
  const dates = useMailDates();
  if (!replyBy) return null;
  const { label, isOverdue } = dates.replyBy(replyBy);
  return <Badge variant={isOverdue ? "destructive" : "secondary"}>{label}</Badge>;
}

function KeyPoints({ points }: { points: string[] }) {
  if (points.length === 0) return null;
  return (
    <ul className="mt-1 flex list-disc flex-col gap-1 ps-4 text-muted-foreground text-xs">
      {points.map((point) => (
        <li key={point} dir="auto">
          {point}
        </li>
      ))}
    </ul>
  );
}

/** The step Leo prepared, and archiving once the email is dealt with. */
function InsightFooter({ mail, view }: LeoInsightCardProps) {
  const t = useTranslations("mailLeo.card");
  const words = useMailWords();
  const canArchive = mail.folder === "inbox";
  if (!canArchive && !mail.repliedAt) return null;

  return (
    <CardFooter className="gap-2">
      <NextAction mail={mail} view={view} />
      {canArchive ? (
        <Button
          variant="ghost"
          size="sm"
          className="ms-auto"
          onClick={() => mailActions.moveTo(mail.id, "archive", words)}
        >
          <Archive data-icon="inline-start" />
          {t("archive")}
        </Button>
      ) : null}
    </CardFooter>
  );
}

/** A draft to review, a note that this reply is the user's to write, or when they replied. */
function NextAction({ mail, view }: LeoInsightCardProps) {
  const t = useTranslations("mailLeo.card");
  const { listDate } = useMailDates();

  if (mail.repliedAt) {
    const replied = listDate(mail.repliedAt);
    return (
      <span className="flex items-center gap-1.5 text-muted-foreground text-xs">
        <Check className="size-3.5" aria-hidden="true" />
        {replied.isRecent ? t("repliedAgo", { ago: replied.text }) : t("repliedOn", { date: replied.text })}
      </span>
    );
  }

  if (view.draft !== null) {
    return (
      <Button size="sm" onClick={() => reviewDraft(mail.id)}>
        <PenLine data-icon="inline-start" />
        {t("reviewDraft")}
      </Button>
    );
  }

  if (view.triage === "needs_you") {
    return <span className="text-muted-foreground text-xs">{t("noDraft")}</span>;
  }

  return null;
}
