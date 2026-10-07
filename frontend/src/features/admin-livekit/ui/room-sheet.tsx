"use client";

import { useState } from "react";

import { PhoneOff, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { LiveKitRoom } from "../domain/contract";
import { formatTime, participantsLabel } from "../domain/format";
import { endRoom, removeParticipant, roomResource } from "../model/livekit-store";
import { ConfirmActionDialog, type RoomAction } from "./confirm-action-dialog";
import { ParticipantsBody } from "./participants-body";

/** Participants of one room with the moderation actions; mounted only while the sheet is open. */
function RoomDetails({ room, onEnded }: { room: LiveKitRoom; onEnded: () => void }) {
  const state = usePollingResource(roomResource(room.name));
  // The last action stays set while the dialog animates out, so its text doesn't change mid-close.
  const [confirm, setConfirm] = useState<RoomAction | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  /** "room" while ending the room, otherwise the identity being disconnected. */
  const [busy, setBusy] = useState<string | null>(null);

  function ask(action: RoomAction) {
    setConfirm(action);
    setConfirmOpen(true);
  }

  async function runConfirmed() {
    const action = confirm;
    setConfirmOpen(false);
    if (!action) return;
    if (action.kind === "room") {
      setBusy("room");
      const ended = await endRoom(room);
      setBusy(null);
      if (ended) onEnded();
      return;
    }
    const { participant } = action;
    setBusy(participant.identity);
    await removeParticipant(room.name, participant);
    setBusy(null);
  }

  const count = state.status === "ready" ? state.data.participants.length : room.num_participants;

  return (
    <>
      <SheetHeader className="border-b pr-12">
        <SheetTitle className="truncate">{room.title}</SheetTitle>
        <SheetDescription>
          Началась в {formatTime(room.started_at)} · {participantsLabel(count)}
        </SheetDescription>
        <p className="truncate font-mono text-muted-foreground text-xs">{room.name}</p>
      </SheetHeader>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4">
        <ParticipantsBody
          state={state}
          busy={busy}
          onRetry={() => void roomResource(room.name).refresh()}
          onRemove={(participant) => ask({ kind: "participant", participant })}
        />
      </div>

      <SheetFooter className="border-t">
        <Button variant="destructive" disabled={busy !== null} onClick={() => ask({ kind: "room" })}>
          {busy === "room" ? <Spinner aria-label="Завершаем" /> : <PhoneOff aria-hidden="true" />}
          Завершить комнату
        </Button>
      </SheetFooter>

      <ConfirmActionDialog
        action={confirm}
        roomTitle={room.title}
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void runConfirmed()}
      />
    </>
  );
}

type RoomSheetProps = {
  room: LiveKitRoom | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function RoomSheet({ room, open, onOpenChange }: RoomSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent showCloseButton={false} className="w-full gap-0 sm:max-w-md">
        {room ? <RoomDetails room={room} onEnded={() => onOpenChange(false)} /> : null}
        <SheetClose asChild>
          <Button variant="ghost" size="icon-sm" className="absolute top-3 right-3">
            <X aria-hidden="true" />
            <span className="sr-only">Закрыть</span>
          </Button>
        </SheetClose>
      </SheetContent>
    </Sheet>
  );
}
