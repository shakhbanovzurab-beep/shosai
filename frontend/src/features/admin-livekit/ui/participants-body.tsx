"use client";

import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

import type { LiveKitParticipant, LiveKitRoomDetail } from "../domain/contract";
import { ParticipantItem } from "./participant-item";

const byJoinTime = (a: LiveKitParticipant, b: LiveKitParticipant) => a.joined_at.localeCompare(b.joined_at);

const PARTICIPANTS_SKELETON = (
  <div className="flex flex-col gap-2" aria-busy="true">
    <span className="sr-only">Загрузка участников…</span>
    <Skeleton className="h-32 rounded-lg" />
    <Skeleton className="h-32 rounded-lg" />
    <Skeleton className="h-32 rounded-lg" />
  </div>
);

type ParticipantsBodyProps = {
  state: ResourceState<LiveKitRoomDetail>;
  busy: string | null;
  onRetry: () => void;
  onRemove: (participant: LiveKitParticipant) => void;
};

/** The room's participants, or its loading, error or empty state. */
export function ParticipantsBody({ state, busy, onRetry, onRemove }: ParticipantsBodyProps) {
  if (state.status === "loading") return PARTICIPANTS_SKELETON;
  if (state.status === "error")
    return (
      <Empty className="border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <CircleAlert aria-hidden="true" />
          </EmptyMedia>
          <EmptyTitle>Не удалось загрузить участников</EmptyTitle>
          <EmptyDescription>{state.message}</EmptyDescription>
        </EmptyHeader>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Повторить
        </Button>
      </Empty>
    );
  if (state.data.participants.length === 0)
    return (
      <p className="py-10 text-center text-muted-foreground text-sm">
        В комнате никого нет. LiveKit закроет её после тайм-аута пустой комнаты.
      </p>
    );
  return (
    <ul aria-label="Участники" className="flex flex-col gap-2 pb-2">
      {state.data.participants.toSorted(byJoinTime).map((participant) => (
        <ParticipantItem
          key={participant.identity}
          participant={participant}
          removing={busy === participant.identity}
          disabled={busy !== null}
          onRemove={() => onRemove(participant)}
        />
      ))}
    </ul>
  );
}
