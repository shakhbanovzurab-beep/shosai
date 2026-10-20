"use client";

import { useState } from "react";

import { FilterX, Settings2, Share2, Video } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";
import { useTimeZone } from "@/i18n/time-zone";
import { Link } from "@/lib/navigation";

import { filterMeetings, groupByRecency, type LibraryQuery, librarySearch } from "../../domain/library";
import { visibleTeams } from "../../domain/people";
import { useMeetings, useResources, useWorkspace } from "../../model/use-workspace";
import { EmptyMessage } from "../shared/empty-message";
import { TeamPage, TeamPageHeader, TeamSection } from "../shared/layout";
import { replaceUrl } from "../shared/replace-url";
import { slugId } from "../shared/slug-id";
import { LibraryToolbar } from "./library-toolbar";
import { MeetingRow } from "./meeting-row";
import { ShareRecordingDialog } from "./share-recording-dialog";

/** `groupByRecency` names its groups in English; these are their catalog keys ("Earlier" is the rest). */
const RECENCY_KEYS: Record<string, "thisWeek" | "lastWeek"> = { "This week": "thisWeek", "Last week": "lastWeek" };

function Loading() {
  const t = useTranslations("workspaceMeetings");
  return (
    <div className="flex flex-col gap-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-32 rounded-xl" />
      <Skeleton className="h-32 rounded-xl" />
    </div>
  );
}

/**
 * The workspace's meeting library: recordings members shared here, filtered by team, by whether you
 * were there, or by words. Your own recordings stay in your Notes until you share one.
 */
export function TeamMeetingsScreen({ initialQuery }: { initialQuery: LibraryQuery }) {
  const { slug, state, can, path } = useWorkspace();
  const meetings = useMeetings();
  const resources = useResources();
  const now = useNow();
  const zone = useTimeZone();
  const [query, setQuery] = useState(initialQuery);
  const [sharing, setSharing] = useState(false);
  const teams = visibleTeams(state, can.me, can.admin);
  const t = useTranslations("workspaceMeetings");
  const shareButton = (
    <Button onClick={() => setSharing(true)}>
      <Share2 data-icon="inline-start" />
      {t("shareMeeting")}
    </Button>
  );

  const change = (next: LibraryQuery) => {
    setQuery(next);
    replaceUrl(path(`/meetings${librarySearch(next)}`));
  };

  let body: React.ReactNode = <Loading />;
  if (meetings.status === "error")
    body = (
      <LoadError title={t("loadFailed")} message={meetings.message} onRetry={() => void resources.meetings.refresh()} />
    );
  else if (meetings.status === "ready" && now !== null) {
    const all = meetings.data.meetings;
    const shown = filterMeetings(all, query, state.me_id);
    if (all.length === 0)
      body = (
        <EmptyMessage
          icon={Video}
          title={t("empty.title")}
          text={t("empty.text", { workspace: state.workspace.name })}
          action={
            <>
              {shareButton}
              {can.editSettings ? (
                <Button asChild variant="ghost">
                  <Link href={path("/settings#sharing")}>{t("reviewSharingRules")}</Link>
                </Button>
              ) : null}
            </>
          }
        />
      );
    else if (shown.length === 0)
      body = (
        <EmptyMessage
          icon={FilterX}
          title={t("noMatch.title")}
          text={t("noMatch.text")}
          action={
            <Button variant="outline" onClick={() => change({ scope: "all", team: null, q: "" })}>
              {t("noMatch.clear")}
            </Button>
          }
        />
      );
    else
      body = (
        <div className="flex flex-col gap-8">
          {groupByRecency(shown, (m) => m.started_at, now, zone).map((group) => (
            <TeamSection
              key={group.label}
              id={slugId("meetings", group.label)}
              title={t(`recency.${RECENCY_KEYS[group.label] ?? "earlier"}`)}
            >
              <ul className="flex flex-col gap-3">
                {group.items.map((meeting) => (
                  <MeetingRow
                    key={meeting.id}
                    meeting={meeting}
                    now={now}
                    slug={slug}
                    meId={state.me_id}
                    members={state.members}
                    teams={state.teams}
                    projects={state.projects}
                    workspaceName={state.workspace.name}
                  />
                ))}
              </ul>
            </TeamSection>
          ))}
        </div>
      );
  }

  return (
    <TeamPage>
      <TeamPageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <>
            {can.editSettings ? (
              <Button asChild variant="outline">
                <Link href={path("/settings#sharing")}>
                  <Settings2 data-icon="inline-start" />
                  {t("sharingRules")}
                </Link>
              </Button>
            ) : null}
            {shareButton}
          </>
        }
      />
      <LibraryToolbar query={query} teams={teams} onChange={change} searchLabel={t("searchMeetings")} withScope />
      {body}
      <ShareRecordingDialog open={sharing} onOpenChange={setSharing} />
    </TeamPage>
  );
}
