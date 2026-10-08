"use client";

import { Mic, MicOff, X } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import type { useLeoVoice } from "../model/use-leo-voice";

const PHASE_ORBS = {
  off: "breathing",
  unavailable: "breathing",
  listening: "listening",
  thinking: "solving",
  speaking: "composing",
} as const;

export function LeoVoiceMode({ voice }: { readonly voice: ReturnType<typeof useLeoVoice> }) {
  const { phase, transcript, muted, unavailableReason, end, toggleMute } = voice;
  const isUnavailable = phase === "unavailable";
  const t = useTranslations("leo");
  const phaseLabels = {
    off: "",
    unavailable: t("voice.unavailable"),
    listening: t("voice.listening"),
    thinking: t("voice.thinking"),
    speaking: t("voice.speaking"),
  };
  const label = muted && phase === "listening" ? t("voice.micOff") : phaseLabels[phase];

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-between gap-6 px-6 py-8">
      <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
        <span className="flex [&_canvas]:size-40!" aria-hidden="true">
          <ThinkingOrb state={muted ? "breathing" : PHASE_ORBS[phase]} size={64} />
        </span>
        <div className="flex flex-col gap-2" aria-live="polite">
          <p className="font-medium text-base">{label}</p>
          <p className="line-clamp-3 min-h-10 max-w-sm text-muted-foreground text-sm">
            {isUnavailable ? unavailableReason : transcript}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="icon-lg"
          className="size-12 rounded-full"
          aria-label={muted ? t("voice.turnMicOn") : t("voice.turnMicOff")}
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
          aria-label={t("voice.end")}
          onClick={end}
        >
          <X />
        </Button>
      </div>
    </div>
  );
}
