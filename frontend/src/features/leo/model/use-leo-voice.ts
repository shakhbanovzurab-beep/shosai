"use client";

import * as React from "react";

import { useTranslations } from "use-intl";

import type { VoiceEnd, VoiceServerFrame } from "../domain/voice-wire";
import { openVoiceAudio, type VoiceAudio } from "./voice/voice-audio";
import { VoiceSocket, type VoiceTarget } from "./voice/voice-socket";

/*
 * Голосовой режим Leo — разговор с Gemini Live голосом Charon через сервер (ADR 0070). Хук держит микрофон,
 * динамик и сокет; фазу ведут кадры сервера и сам звук: «говорит» — пока играет голос Leo. Перебил человек —
 * голос Leo замолкает сразу. Закончился разговор — тред перечитывается: в нём уже записаны реплики.
 */

export type LeoVoicePhase = "off" | "connecting" | "unavailable" | "listening" | "thinking" | "speaking";

interface UseLeoVoiceOptions {
  /** Куда говорить: пространство и тред панели; null — у этого разговора голоса нет. */
  readonly target: VoiceTarget | null;
  /** Разговор закончился: реплики уже в треде, который назвал сервер. */
  readonly onEnded: (threadId: string | null) => void;
}

type Live = { readonly socket: VoiceSocket; readonly audio: VoiceAudio };

/** Голос Leo зазвучал — «говорит»; очередь опустела — снова «слушаю», если он говорил. */
function phaseWhenSpeech(now: LeoVoicePhase, playing: boolean): LeoVoicePhase {
  if (playing) return "speaking";
  return now === "speaking" ? "listening" : now;
}

export function useLeoVoice({ target, onEnded }: UseLeoVoiceOptions) {
  const t = useTranslations("leoVoice");
  const [phase, setPhase] = React.useState<LeoVoicePhase>("off");
  const [transcript, setTranscript] = React.useState("");
  const [muted, setMuted] = React.useState(false);
  const [unavailableReason, setUnavailableReason] = React.useState("");
  // Leo подготовил действие: карточка ждёт решения в чате.
  const [proposed, setProposed] = React.useState(false);
  // Громкость микрофона меняется 50 раз в секунду: сфера читает её из ref, без перерисовок.
  const level = React.useRef(0);
  const live = React.useRef<Live | null>(null);

  const unavailable = (reason: string) => {
    setUnavailableReason(reason);
    setPhase("unavailable");
  };

  const finish = (end: VoiceEnd) => {
    const current = live.current;
    live.current = null;
    void current?.audio.close();
    level.current = 0;
    setTranscript("");
    onEnded(current?.socket.threadId ?? target?.threadId ?? null);
    if (end === "ended") setPhase("off");
    else unavailable(t(`endReason.${end}`));
  };

  const handle = (frame: VoiceServerFrame) => {
    switch (frame.type) {
      case "ready":
        setPhase("listening");
        break;
      case "state":
        // «Говорит» ведёт сам звук: сервер шлёт речь раньше, чем она прозвучит.
        if (frame.state !== "speaking") setPhase(frame.state);
        break;
      case "transcript":
        setTranscript(frame.text);
        break;
      case "interrupted":
        live.current?.audio.flush();
        setPhase("listening");
        break;
      case "action.proposed":
        setProposed(true);
        break;
      default:
        break;
    }
  };

  const start = async () => {
    if (target === null) return;
    if (!window.isSecureContext) return unavailable(t("needsHttps"));
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === "undefined") {
      return unavailable(t("unsupported"));
    }
    setMuted(false);
    setProposed(false);
    setPhase("connecting");
    const socket = new VoiceSocket(target, {
      frame: handle,
      audio: (pcm) => live.current?.audio.play(pcm),
      ended: finish,
    });
    try {
      const audio = await openVoiceAudio({
        frame: (frame) => socket.send(frame),
        level: (value) => {
          level.current = value;
        },
        speaking: (playing) => setPhase((now) => phaseWhenSpeech(now, playing)),
      });
      live.current = { socket, audio };
    } catch (error) {
      const blocked = error instanceof DOMException && error.name === "NotAllowedError";
      return unavailable(t(blocked ? "micBlocked" : "unsupported"));
    }
    await socket.open();
  };

  const end = () => {
    if (live.current === null) {
      setPhase("off");
      return;
    }
    live.current.socket.close();
  };

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    live.current?.audio.setMuted(next);
  };

  React.useEffect(
    () => () => {
      live.current?.socket.close();
      void live.current?.audio.close();
    },
    [],
  );

  return {
    phase,
    transcript,
    muted,
    proposed,
    level,
    unavailableReason,
    start,
    end,
    toggleMute,
    isActive: phase !== "off",
  };
}
