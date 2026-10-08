"use client";

import { Archive, CheckCheck } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

import type { MailInsightsResponse } from "../domain/leo-insights";
import type { InboxBrief, LeoMailView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { insightsResource } from "../model/leo-insights";
import { mailActions } from "../model/mail-store";
import { LeoInboxStatus } from "./leo-inbox-status";
import { MailList } from "./mail-list";
import { useMailWords } from "./use-mail-words";

type LeoFocusListProps = {
  state: ResourceState<MailInsightsResponse>;
  views: ReadonlyMap<string, LeoMailView>;
  brief: InboxBrief;
  onSelectMail?: (mail: Mail) => void;
  onShowAll: () => void;
};

/** The "Needs you" view: emails waiting on the user, most urgent first, each with Leo's next step. */
export function LeoFocusList({ state, views, brief, onSelectMail, onShowAll }: LeoFocusListProps) {
  const t = useTranslations("mailLeo");

  if (state.status === "error") {
    return (
      <div className="px-2">
        <LoadError
          title={t("status.sortFailed")}
          message={state.message}
          onRetry={() => void insightsResource.refresh()}
        />
      </div>
    );
  }

  const isReading = state.status === "loading" || (brief.waiting.length === 0 && brief.analyzing > 0);

  return (
    <>
      <div className="px-3">
        <LeoInboxStatus state={state} brief={brief} />
      </div>
      {isReading ? <FocusSkeleton /> : null}
      {!isReading && brief.waiting.length === 0 ? <CaughtUp brief={brief} onShowAll={onShowAll} /> : null}
      {!isReading && brief.waiting.length > 0 ? (
        <MailList
          groups={[
            {
              id: "needs-you",
              title: t("focus.mostUrgentFirst", { count: brief.waiting.length }),
              items: brief.waiting,
            },
          ]}
          views={views}
          inboxView="focus"
          onSelectMail={onSelectMail}
          footer={<SetAside brief={brief} onShowAll={onShowAll} />}
        />
      ) : null}
    </>
  );
}

const SKELETON_ROWS = ["first", "second", "third"];

function FocusSkeleton() {
  return (
    <div className="flex flex-col gap-5 p-3" aria-hidden="true">
      {SKELETON_ROWS.map((row) => (
        <div key={row} className="flex items-start gap-3">
          <Skeleton className="size-9 rounded-sm" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ArchiveLowPriority({ ids }: { ids: readonly string[] }) {
  const t = useTranslations("mailLeo.focus");
  const words = useMailWords();
  if (ids.length === 0) return null;
  return (
    <Button variant="ghost" size="xs" onClick={() => mailActions.archiveMany(ids, words)}>
      <Archive data-icon="inline-start" />
      {t("archiveLow")}
    </Button>
  );
}

/** Closes the queue: what Leo kept out of the way, and a one-click tidy-up for the low-priority part. */
function SetAside({ brief, onShowAll }: { brief: InboxBrief; onShowAll: () => void }) {
  const t = useTranslations("mailLeo.focus");
  if (brief.canWait === 0) return null;
  const low = brief.lowPriority.length;

  return (
    <div className="mx-3 mt-1.5 mb-3 flex flex-col gap-2 rounded-lg border border-dashed p-3">
      <p className="text-muted-foreground text-xs leading-5">
        {low > 0 ? t("setAsideLow", { count: brief.canWait, low }) : t("setAside", { count: brief.canWait })}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="xs" onClick={onShowAll}>
          {t("showAll")}
        </Button>
        <ArchiveLowPriority ids={brief.lowPriority} />
      </div>
    </div>
  );
}

function CaughtUp({ brief, onShowAll }: { brief: InboxBrief; onShowAll: () => void }) {
  const t = useTranslations("mailLeo.focus");

  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CheckCheck />
        </EmptyMedia>
        <EmptyTitle>{t("caughtUpTitle")}</EmptyTitle>
        <EmptyDescription>{t("caughtUpDescription")}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="outline" size="sm" onClick={onShowAll}>
            {t("showAll")}
          </Button>
          <ArchiveLowPriority ids={brief.lowPriority} />
        </div>
      </EmptyContent>
    </Empty>
  );
}
