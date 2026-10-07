import { Check, PenLine } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";

import type { InboxView, LeoMailView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { useMailDates } from "./use-mail-dates";

type LeoMailTagsProps = {
  mail: Mail;
  view: LeoMailView | undefined;
  inboxView: InboxView;
};

/** Leo's tags under a message: still reading it, waiting on you (and by when), a draft ready, or replied. */
export function LeoMailTags({ mail, view, inboxView }: LeoMailTagsProps) {
  const t = useTranslations("mailLeo.tags");
  const dates = useMailDates();
  if (!view) return null;

  if (view.insight.status === "analyzing") {
    return (
      <div className="flex">
        <Badge variant="outline">
          <span className="shimmer">{t("reading")}</span>
        </Badge>
      </div>
    );
  }

  if (mail.repliedAt) {
    return (
      <div className="flex">
        <Badge variant="outline">
          <Check data-icon="inline-start" />
          {t("replied")}
        </Badge>
      </div>
    );
  }

  if (view.triage !== "needs_you") return null;

  // The "Needs you" view already says it needs you, so it shows the deadline instead.
  const replyBy = inboxView === "focus" && view.insight.reply_by ? dates.replyBy(view.insight.reply_by) : null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {inboxView === "all" ? <Badge>{t("needsYou")}</Badge> : null}
      {replyBy ? <Badge variant={replyBy.isOverdue ? "destructive" : "secondary"}>{replyBy.label}</Badge> : null}
      {view.draft ? (
        <Badge variant="outline">
          <PenLine data-icon="inline-start" />
          {t("draftReady")}
        </Badge>
      ) : null}
    </div>
  );
}
