"use client";

import { cn } from "cn";
import { CircleAlert } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import type { ResourceState } from "@/lib/polling-resource";

import type { MailInsightsResponse } from "../domain/leo-insights";
import type { InboxBrief } from "../domain/leo-triage";
import { insightsResource } from "../model/leo-insights";

type LeoInboxStatusProps = {
  state: ResourceState<MailInsightsResponse>;
  brief: InboxBrief;
};

/** One line from Leo above the list: what it is reading, what it has sorted, or that it couldn't. */
export function LeoInboxStatus({ state, brief }: LeoInboxStatusProps) {
  const t = useTranslations("mailLeo.status");
  const common = useTranslations("common");

  if (state.status === "error") {
    return (
      <div className="flex h-6 items-center gap-2 text-muted-foreground text-xs" role="status">
        <CircleAlert className="size-4 shrink-0 text-destructive" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate">{t("sortFailed")}</span>
        <Button variant="ghost" size="xs" onClick={() => void insightsResource.refresh()}>
          {common("actions.retry")}
        </Button>
      </div>
    );
  }

  const isReading = state.status === "loading" || brief.analyzing > 0;

  return (
    <div className="flex h-6 items-center gap-2 text-muted-foreground text-xs" role="status">
      <ThinkingOrb state={isReading ? "searching" : "breathing"} size={20} aria-hidden="true" />
      <span className={cn("min-w-0 truncate", isReading && "shimmer")}>{describe(state, brief, t)}</span>
    </div>
  );
}

type StatusWords = ReturnType<typeof useTranslations<"mailLeo.status">>;

function describe(state: ResourceState<MailInsightsResponse>, brief: InboxBrief, t: StatusWords) {
  if (state.status === "loading") return t("readingInbox");
  if (brief.analyzing > 0) return t("readingNew", { count: brief.analyzing });
  if (brief.drafts === 0) return t("sorted", { count: brief.sorted });
  return t("sortedWithDrafts", { count: brief.sorted, drafts: brief.drafts });
}
