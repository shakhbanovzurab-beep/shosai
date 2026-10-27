"use client";

import { MessageSquare, Mic, MicOff, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import type { useLeoVoice } from "../model/use-leo-voice";
import { LeoVoiceOrb } from "./leo-voice-orb";

const ORB_SIZE = 160;

const PHASE_ORBS = {
  off: "breathing",
  connecting: "connecting",
  unavailable: "breathing",
  listening: "listening",
  thinking: "solving",
  speaking: "composing",
} as const;

/** Голосовой режим: сфера, что сейчас происходит, последняя реплика и кнопки микрофона и конца разговора. */
export function LeoVoiceMode({ voice }: { readonly voice: ReturnType<typeof useLeoVoice> }) {
  const { phase, transcript, muted, proposed, level, unavailableReason, end, toggleMute } = voice;
  const isUnavailable = phase === "unavailable";
  const t = useTranslations("leoVoice");
  const phaseLabels = {
    off: "",
    connecting: t("connecting"),
    unavailable: t("unavailable"),
    listening: t("listening"),
    thinking: t("thinking"),
    speaking: t("speaking"),
  };
  const label = muted && phase === "listening" ? t("micOff") : phaseLabels[phase];

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-between gap-6 px-6 py-8">
      <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
        <span className="flex" aria-hidden="true">
          <LeoVoiceOrb state={muted ? "breathing" : PHASE_ORBS[phase]} size={ORB_SIZE} level={level} />
        </span>
        <div className="flex flex-col gap-2" aria-live="polite">
          <p className="font-medium text-base">{label}</p>
          <p className="line-clamp-3 min-h-10 max-w-sm text-muted-foreground text-sm" dir="auto">
            {isUnavailable ? unavailableReason : transcript}
          </p>
        </div>
        {proposed ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border bg-card px-4 py-3 text-sm">
            <p>{t("proposed")}</p>
            <Button variant="outline" size="sm" onClick={end}>
              <MessageSquare data-icon="inline-start" />
              {t("openChat")}
            </Button>
          </div>
        ) : null}
      </div>

      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="icon-lg"
          className="size-12 rounded-full"
          aria-label={muted ? t("turnMicOn") : t("turnMicOff")}
          aria-pressed={muted}
          disabled={isUnavailable}
          onClick={toggleMute}
        >
          {muted ? <MicOff /> : <Mic />}
        </Button>
        <Button
          variant="destructive"
          size="icon-lg"
          className="size-12 rounded-full"
          aria-label={t("end")}
          onClick={end}
        >
          <X />
        </Button>
      </div>
    </div>
  );
}
