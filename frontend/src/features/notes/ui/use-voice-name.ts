"use client";

import { useTranslations } from "use-intl";

import type { Voice } from "../domain/meeting-page";

/** Подпись голоса на языке человека: «Вы» на своей встрече, «Организатор» на чужой, «Спикер N» у остальных. */
export function useVoiceName() {
  const t = useTranslations("notesNote");
  return (owned: boolean) =>
    (voice: Voice): string => {
      switch (voice.kind) {
        case "owner":
          return owned ? t("transcript.you") : t("transcript.organizer");
        case "number":
          return t("transcript.speaker", { n: voice.n });
        case "unknown":
          return t("transcript.unknownSpeaker");
      }
    };
}
