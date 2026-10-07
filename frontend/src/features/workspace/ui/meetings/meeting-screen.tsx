"use client";

import Link from "next/link";

import {
  ArrowLeft,
  CalendarDays,
  Clock,
  FolderKanban,
  NotebookText,
  ScrollText,
  ShieldQuestion,
  Users,
} from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NoteTranscript } from "@/features/notes";
import { useNow } from "@/hooks/use-now";

import type { TeamMeetingDetail } from "../../domain/content-contract";
import { projectPath } from "../../domain/paths";
import { useMeetingDetail, useResources, useWorkspace } from "../../model/use-workspace";
import { EmptyMessage } from "../shared/empty-message";
import { TeamPage } from "../shared/layout";
import { MeetingSummary } from "./meeting-summary";
import { ShareControl } from "./share-control";
import { useMeetingWhen } from "./use-meeting-when";

function BackLink({ href }: { href: string }) {
  const t = useTranslations("workspaceMeetings.meeting");
  return (
    <Button variant="ghost" size="sm" className="-ms-2 w-fit text-muted-foreground" asChild>
      <Link href={href}>
        <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
        {t("back")}
      </Link>
    </Button>
  );
}

function Meta({ icon: Icon, label, children }: { icon: typeof Clock; label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <dt className="sr-only">{label}</dt>
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <dd className="min-w-0 truncate">{children}</dd>
    </div>
  );
}

function MeetingBody({ meeting, now }: { meeting: TeamMeetingDetail; now: number }) {
  const { slug, state } = useWorkspace();
  const organizer = state.members.find((m) => m.id === meeting.organizer_id);
  const project = state.projects.find((p) => p.id === meeting.project_id);
  const guests = meeting.participants.filter((p) => p.member_id === null).length;
  const t = useTranslations("workspaceMeetings.meeting");
  const format = useFormatter();
  const when = useMeetingWhen();
  const names = format.list(
    meeting.participants.map((p) => p.name),
    { type: "unit", style: "short" },
  );
  return (
    <article className="flex flex-col gap-6" aria-labelledby="meeting-title">
      <header className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <h1
            id="meeting-title"
            dir="auto"
            className="text-balance font-semibold text-2xl leading-tight tracking-tight"
          >
            {meeting.title}
          </h1>
          <ShareControl meeting={meeting} />
        </div>
        <dl className="flex flex-wrap gap-x-5 gap-y-2 text-muted-foreground text-sm">
          <Meta icon={CalendarDays} label={t("date")}>
            <time dateTime={meeting.started_at}>
              {when.day(meeting.started_at, now)} · {when.clock(meeting.started_at)}
            </time>
          </Meta>
          <Meta icon={Clock} label={t("duration")}>
            {when.duration(meeting.duration_minutes)}
          </Meta>
          <Meta icon={Users} label={t("participants")}>
            <span dir="auto">
              {guests > 0
                ? t("participantsWithGuests", { names, count: guests, workspace: state.workspace.name })
                : names}
            </span>
          </Meta>
          {project ? (
            <Meta icon={FolderKanban} label={t("project")}>
              <Link
                href={projectPath(slug, project.id)}
                dir="auto"
                className="underline-offset-4 hover:text-foreground hover:underline"
              >
                {project.name}
              </Link>
            </Meta>
          ) : null}
        </dl>
        {organizer ? (
          <p className="text-muted-foreground text-xs">
            {organizer.id === state.me_id ? t("recordedByYou") : t("sharedBy", { name: organizer.name })}
          </p>
        ) : null}
      </header>
      <Tabs defaultValue="summary" className="gap-6">
        <TabsList variant="line" className="w-full justify-start border-b">
          <TabsTrigger value="summary" className="flex-none">
            <NotebookText />
            {t("summary")}
          </TabsTrigger>
          <TabsTrigger value="transcript" className="flex-none">
            <ScrollText />
            {t("transcript")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="summary">
          <MeetingSummary meeting={meeting} now={now} />
        </TabsContent>
        <TabsContent value="transcript">
          {meeting.transcript ? (
            <NoteTranscript lines={meeting.transcript} />
          ) : (
            <EmptyMessage
              icon={ShieldQuestion}
              title={t("transcriptPrivateTitle")}
              text={organizer ? t("transcriptPrivate", { name: organizer.name }) : t("transcriptPrivateUnknown")}
            />
          )}
        </TabsContent>
      </Tabs>
    </article>
  );
}

/** A shared meeting on its own page; a missing or private one says so instead of failing. */
export function TeamMeetingScreen({ meetingId }: { meetingId: string }) {
  const { path } = useWorkspace();
  const resources = useResources();
  const meeting = useMeetingDetail(meetingId);
  const now = useNow();
  const t = useTranslations("workspaceMeetings.meeting");

  let body: React.ReactNode = (
    <div className="flex flex-col gap-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="mt-4 h-48 rounded-xl" />
    </div>
  );
  if (meeting.status === "error")
    body = (
      <LoadError
        title={t("loadFailed")}
        message={meeting.message}
        onRetry={() => void resources.meeting(meetingId).refresh()}
      />
    );
  else if (meeting.status === "ready" && meeting.data === null)
    body = (
      <EmptyMessage
        icon={ShieldQuestion}
        title={t("unavailableTitle")}
        text={t("unavailable")}
        action={
          <Button asChild variant="outline">
            <Link href={path("/meetings")}>{t("backToMeetings")}</Link>
          </Button>
        }
      />
    );
  else if (meeting.status === "ready" && meeting.data && now !== null)
    body = <MeetingBody meeting={meeting.data} now={now} />;

  return (
    <TeamPage className="max-w-3xl">
      <BackLink href={path("/meetings")} />
      {body}
    </TeamPage>
  );
}
