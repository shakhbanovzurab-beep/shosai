"use client";

import type { ReactNode } from "react";

import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { MeetingAllowance } from "@/features/upgrade";
import { SharedMeetingsList, SharedMeetingsNav } from "@/features/workspace";
import { useNow } from "@/hooks/use-now";

import { bucketMeetings, type MeetingsView } from "../domain/meeting";
import { meetingsResource, useMeetings } from "../model/meetings-resource";
import { MeetingsContent } from "./meetings-content";
import { MeetingsNav } from "./meetings-nav";
import { NewMeetingButton } from "./new-meeting-button";

function Loading() {
  const t = useTranslations("meetings");
  return (
    <div className="flex flex-col gap-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-36 rounded-xl" />
      <Skeleton className="h-16 rounded-lg" />
      <Skeleton className="h-16 rounded-lg" />
    </div>
  );
}

const sharedHref = (slug: string) => `/app/meetings?workspace=${encodeURIComponent(slug)}`;

/**
 * Your meetings: what's live, what's next and what happened, with Leo's recaps. Planning stays in
 * Calendar and the call itself in the Meeting Room. Meetings teammates shared with you in a workspace
 * are under "Shared with you", apart from your own (`sharedIn` is that workspace's slug).
 */
export function MeetingsScreen({ view, sharedIn }: { view: MeetingsView; sharedIn: string | null }) {
  const t = useTranslations("meetings");
  const state = useMeetings();
  const now = useNow();

  let counts: Record<MeetingsView, number> | null = null;
  let body: ReactNode = <Loading />;
  if (state.status === "error")
    body = (
      // The meetings load in the browser, with no reason worded by a server: say what to do instead.
      <LoadError
        title={t("loadFailed")}
        message={t("loadFailedHint")}
        onRetry={() => void meetingsResource.refresh()}
      />
    );
  else if (state.status === "ready" && now !== null) {
    const buckets = bucketMeetings(state.data, now);
    counts = {
      all: state.data.length,
      upcoming: buckets.upcoming.length,
      live: buckets.live.length,
      past: buckets.past.length,
    };
    body = <MeetingsContent view={view} buckets={buckets} now={now} />;
  }
  if (sharedIn) body = <SharedMeetingsList slug={sharedIn} />;

  return (
    // Bottom padding keeps the last cards clear of the floating Leo button.
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 pb-16">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-semibold text-2xl tracking-tight">{t("title")}</h1>
        <NewMeetingButton />
      </header>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <aside className="flex min-w-0 flex-col gap-4">
          <MeetingsNav view={sharedIn ? null : view} counts={counts} />
          <SharedMeetingsNav activeSlug={sharedIn} hrefFor={sharedHref} />
          <MeetingAllowance />
        </aside>
        <div className="min-w-0">{body}</div>
      </div>
    </div>
  );
}
