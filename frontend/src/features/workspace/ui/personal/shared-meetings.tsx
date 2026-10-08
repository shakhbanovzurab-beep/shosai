"use client";

import { cn } from "cn";
import { Share2, Users } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";
import { Link } from "@/lib/navigation";

import { meetingPath, workspacePath } from "../../domain/paths";
import { useMyMeetings, useMyShares } from "../../model/resources";
import { useMeetingWhen } from "../meetings/use-meeting-when";
import { EmptyMessage } from "../shared/empty-message";
import { WorkspaceTile } from "../switcher/workspace-tile";

/**
 * "Shared with you" under the personal meeting filters: one entry per workspace, counting meetings
 * others shared there. Your own recordings stay in the list above; nothing is mixed in.
 */
export function SharedMeetingsNav({
  activeSlug,
  hrefFor,
}: {
  activeSlug: string | null;
  hrefFor: (slug: string) => string;
}) {
  const feed = useMyMeetings();
  const t = useTranslations("workspacePersonal.sharedMeetings");
  const format = useFormatter();
  if (feed.status !== "ready" || feed.data.workspaces.length === 0) return null;
  return (
    <nav aria-label={t("nav")} className="flex flex-col gap-1">
      <h2 className="hidden px-3 pt-2 font-medium text-muted-foreground text-xs uppercase tracking-wide lg:block">
        {t("nav")}
      </h2>
      <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {feed.data.workspaces.map(({ workspace, meetings }) => {
          const active = workspace.slug === activeSlug;
          return (
            <li key={workspace.id} className="shrink-0">
              <Link
                href={hrefFor(workspace.slug)}
                scroll={false}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                <WorkspaceTile name={workspace.name} className="size-4 text-[9px]" />
                <span className="truncate" dir="auto">
                  {workspace.name}
                </span>
                <span className="ms-auto ps-2 text-muted-foreground text-xs tabular-nums">
                  {format.number(meetings.length)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Meetings others shared with you in one workspace; each opens in the workspace, where it lives. */
export function SharedMeetingsList({ slug }: { slug: string }) {
  const feed = useMyMeetings();
  const now = useNow();
  const t = useTranslations("workspacePersonal.sharedMeetings");
  const row = useTranslations("workspaceMeetings.row");
  const when = useMeetingWhen();
  if (feed.status === "loading" || now === null) return <Skeleton className="h-40 rounded-xl" />;
  if (feed.status === "error") return <p className="text-muted-foreground text-sm">{t("loadFailed")}</p>;
  const entry = feed.data.workspaces.find((w) => w.workspace.slug === slug);
  if (!entry || entry.meetings.length === 0)
    return <EmptyMessage icon={Users} title={t("emptyTitle")} text={t("empty")} />;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-sm">
        {t.rich("intro", {
          workspace: entry.workspace.name,
          link: (chunks) => (
            <Link href={workspacePath(slug)} dir="auto" className="text-foreground underline-offset-4 hover:underline">
              {chunks}
            </Link>
          ),
        })}
      </p>
      <ul className="grid gap-3 md:grid-cols-2">
        {entry.meetings.map((meeting) => (
          <li
            key={meeting.id}
            className="relative flex flex-col gap-2 rounded-xl border bg-card p-4 has-[a:hover]:bg-muted/40"
          >
            <Link
              href={meetingPath(slug, meeting.id)}
              dir="auto"
              className="truncate font-medium outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
            >
              {meeting.title}
            </Link>
            <span className="text-muted-foreground text-xs tabular-nums">
              {when.day(meeting.started_at, now)} · {when.clock(meeting.started_at)} ·{" "}
              {when.duration(meeting.duration_minutes)}
            </span>
            <p className="line-clamp-2 text-muted-foreground text-sm" dir="auto">
              {meeting.summary}
            </p>
            <span className="text-xs">
              {[
                meeting.decision_count ? row("decisions", { count: meeting.decision_count }) : null,
                meeting.task_count ? row("tasks", { count: meeting.task_count }) : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** On one of your recordings: where it's shared, so ownership and reach are visible at a glance. */
export function RecordingShareBadge({ recordingId }: { recordingId: string }) {
  const shares = useMyShares();
  const t = useTranslations("workspacePersonal");
  const share = shares.status === "ready" ? shares.data.recordings.find((r) => r.recording_id === recordingId) : null;
  if (!share) return null;
  return (
    <Badge variant="outline" className="relative z-10 font-normal">
      <Share2 aria-hidden="true" />
      {t("sharedIn", { workspace: share.workspace.name })}
    </Badge>
  );
}
