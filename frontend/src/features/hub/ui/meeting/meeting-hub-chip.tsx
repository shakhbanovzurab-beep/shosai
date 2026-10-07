"use client";

import { useState } from "react";

import Link from "next/link";

import { LayoutGrid, TriangleAlert, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { META_VALUE_BUTTON, MetaItem } from "@/components/meta-item";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { MeetingHub } from "../../domain/contract";
import { hubPath } from "../../domain/paths";
import { retry, useHubList, useMeetingHub } from "../../model/hooks";
import { fileMeeting, unfileMeeting } from "../../model/meeting-actions";
import { useHubWords } from "../../model/words";
import { NameDialog } from "../dialogs/name-dialog";
import { WARNING_INK } from "../shared/urgency-tones";
import { HubPicker } from "./hub-picker";
import { HubSuggestion } from "./hub-suggestion";

/** No hub and no suggestion: file it by hand, or create the first hub when there is none. */
function Unfiled({ meetingId }: { meetingId: string }) {
  const t = useTranslations("hubMeetings");
  const words = useHubWords();
  const hubs = useHubList(false);
  const [picking, setPicking] = useState(false);
  const [creating, setCreating] = useState(false);
  if (hubs.status === "ready" && hubs.data.hubs.length === 0)
    return (
      <>
        <Button variant="ghost" size="xs" className={META_VALUE_BUTTON} onClick={() => setCreating(true)}>
          {t("chip.createFirst")}
        </Button>
        <NameDialog
          hub={null}
          open={creating}
          onOpenChange={setCreating}
          onCreated={(hub) => void fileMeeting(words, meetingId, hub)}
        />
      </>
    );
  return (
    <HubPicker
      current={null}
      open={picking}
      onOpenChange={setPicking}
      onPick={(hub) => void fileMeeting(words, meetingId, hub)}
      trigger={
        <Button variant="ghost" size="xs" className={META_VALUE_BUTTON}>
          {t("chip.fileTo")}
        </Button>
      }
    />
  );
}

type FiledHub = NonNullable<MeetingHub["hub"]>;

/** The meeting's hub: its name links to it, with why it landed there on hover, and a quiet way out. */
function Filed({ meetingId, data, hub }: { meetingId: string; data: MeetingHub; hub: FiledHub }) {
  const t = useTranslations("hubMeetings");
  const detail = useTranslations("hubDetail");
  const words = useHubWords();
  const link = (
    <Link
      href={hubPath(hub.id)}
      dir="auto"
      className="min-w-0 truncate underline-offset-4 hover:text-foreground hover:underline"
    >
      {hub.name}
    </Link>
  );
  return (
    <>
      {data.signal ? (
        <Tooltip>
          <TooltipTrigger asChild>{link}</TooltipTrigger>
          <TooltipContent>{detail(`why.signals.${data.signal}`)}</TooltipContent>
        </Tooltip>
      ) : (
        link
      )}
      {hub.archived ? <span className="shrink-0">· {t("chip.archived")}</span> : null}
      {!hub.archived && hub.boardId === null ? (
        <span className="inline-flex shrink-0 items-center gap-1">
          <TriangleAlert className={`size-3.5 ${WARNING_INK}`} aria-hidden="true" />
          {t("chip.noBoard")}
        </span>
      ) : null}
      <Button
        variant="ghost"
        size="icon-xs"
        className="text-muted-foreground hover:text-foreground"
        aria-label={t("chip.removeLabel", { hub: hub.name })}
        onClick={() => void unfileMeeting(words, meetingId, data)}
      >
        <X />
      </Button>
    </>
  );
}

function Chip({ meetingId, data }: { meetingId: string; data: MeetingHub }) {
  if (data.hub) return <Filed meetingId={meetingId} data={data} hub={data.hub} />;
  if (data.suggestion)
    return <HubSuggestion meetingId={meetingId} hub={data.suggestion.hub} signal={data.suggestion.signal} />;
  return <Unfiled meetingId={meetingId} />;
}

/**
 * The hub of a meeting, as a quiet item in the row under its title. The server never files a meeting
 * it isn't sure about: it suggests, with its reason, and one click files it.
 */
export function MeetingHubChip({ meetingId }: { meetingId: string }) {
  const t = useTranslations("hubMeetings");
  const common = useTranslations("common");
  const api = useTranslations("hubApi");
  const state = useMeetingHub(meetingId);
  let content: React.ReactNode = <Skeleton className="h-4 w-36" aria-label={common("feedback.loading")} />;
  if (state.status === "error")
    content = (
      <>
        <span>{api("errors.unknown")}</span>
        <Button
          variant="ghost"
          size="xs"
          className={META_VALUE_BUTTON}
          onClick={() => void retry.meetingHub(meetingId)}
        >
          {common("actions.retry")}
        </Button>
      </>
    );
  else if (state.status === "ready") content = <Chip meetingId={meetingId} data={state.data} />;
  return (
    <MetaItem icon={LayoutGrid} label={t("chip.label")}>
      {content}
    </MetaItem>
  );
}
