"use client";

import { ConfirmDestructive } from "@/components/feedback";

import type { LiveKitParticipant } from "../domain/contract";

export type RoomAction = { kind: "room" } | { kind: "participant"; participant: LiveKitParticipant };

type ConfirmActionDialogProps = {
  /** Kept after closing so the text doesn't change while the dialog animates out. */
  action: RoomAction | null;
  roomTitle: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
};

/** Confirms ending the room or disconnecting a participant. */
export function ConfirmActionDialog({ action, roomTitle, open, onOpenChange, onConfirm }: ConfirmActionDialogProps) {
  const participant = action?.kind === "participant" ? action.participant : null;
  return (
    <ConfirmDestructive
      open={open}
      title={participant ? "Отключить участника?" : "Завершить комнату?"}
      description={
        participant
          ? `${participant.name} будет отключён от встречи «${roomTitle}». Он сможет подключиться снова по ссылке.`
          : `Встреча «${roomTitle}» закончится для всех участников. Идущая запись будет остановлена и сохранена.`
      }
      confirmLabel={participant ? "Отключить" : "Завершить"}
      cancelLabel="Отмена"
      onConfirm={onConfirm}
      onCancel={() => onOpenChange(false)}
    />
  );
}
