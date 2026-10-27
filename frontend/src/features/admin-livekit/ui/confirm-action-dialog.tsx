"use client";

import { ConfirmDestructive } from "@/components/feedback";

import type { LiveKitParticipant } from "../domain/contract";

export type RoomAction = { kind: "room" } | { kind: "participant"; participant: LiveKitParticipant };

type ConfirmActionDialogProps = {
  /** Kept after closing so the text doesn't change while the dialog animates out. */
  action: RoomAction | null;
  roomName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
};

/** Confirms ending the room or disconnecting a participant. */
export function ConfirmActionDialog({ action, roomName, open, onOpenChange, onConfirm }: ConfirmActionDialogProps) {
  const participant = action?.kind === "participant" ? action.participant : null;
  return (
    <ConfirmDestructive
      open={open}
      title={participant ? "Отключить участника?" : "Завершить комнату?"}
      description={
        participant
          ? `${participant.name} будет отключён от комнаты ${roomName} на всех устройствах и больше не сможет в неё войти.`
          : `Встреча в комнате ${roomName} закончится для всех участников, комната закроется навсегда. Идущая запись будет остановлена и сохранена.`
      }
      confirmLabel={participant ? "Отключить" : "Завершить"}
      cancelLabel="Отмена"
      onConfirm={onConfirm}
      onCancel={() => onOpenChange(false)}
    />
  );
}
