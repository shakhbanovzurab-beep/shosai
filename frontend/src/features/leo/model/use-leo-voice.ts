"use client";

import * as React from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { useUiLanguage } from "@/hooks/use-ui-language";

import type { LeoMessage } from "../domain/types";

// The Web Speech recognition API is not in TypeScript's DOM lib yet; this is the subset Leo uses.
interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  abort: () => void;
  onresult: ((event: { results: SpeechRecognitionResultList }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getRecognitionConstructor(): SpeechRecognitionConstructor | undefined {
  const scope = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
}

export type LeoVoicePhase = "off" | "unavailable" | "listening" | "thinking" | "speaking";

interface UseLeoVoiceOptions {
  // Resolves with Leo's finished reply, so voice mode can read it out as soon as it is ready.
  readonly onSend: (content: string) => Promise<LeoMessage | undefined>;
  /** The language Leo's answers are written in: the reply is read out in it. */
  readonly answerLanguage: string;
}

export function useLeoVoice({ onSend, answerLanguage }: UseLeoVoiceOptions) {
  const t = useTranslations("leo");
  // The user is heard in the interface language; Leo's answer is read out in the language it is written in.
  const speechLanguage = useUiLanguage();
  const [phase, setPhase] = React.useState<LeoVoicePhase>("off");
  const [transcript, setTranscript] = React.useState("");
  const [muted, setMuted] = React.useState(false);
  const [unavailableReason, setUnavailableReason] = React.useState("");
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null);
  const activeRef = React.useRef<boolean>(false);
  const mutedRef = React.useRef<boolean>(false);

  // A function, not an inline ref read: voice mode can end while a reply or a recognition is still pending.
  const isVoiceActive = () => activeRef.current;

  const stopListening = () => {
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    if (recognition) {
      recognition.onend = null;
      recognition.abort();
    }
  };

  const listen = () => {
    const Recognition = getRecognitionConstructor();
    if (!Recognition || !activeRef.current || mutedRef.current) return;

    let finalText = "";
    const recognition = new Recognition();
    recognition.lang = speechLanguage;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const text = Array.from(event.results, (result) => result[0].transcript).join("");
      setTranscript(text);
      if (event.results[event.results.length - 1].isFinal) finalText = text;
    };
    recognition.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        toast.error(t("voice.micBlocked"), { description: t("voice.micBlockedHint") });
        end();
      }
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      if (!isVoiceActive()) return;
      if (finalText.trim()) {
        setPhase("thinking");
        void onSend(finalText.trim()).then(handleReply);
      } else {
        // Nothing was said before the browser timed out: keep listening.
        listen();
      }
    };

    recognitionRef.current = recognition;
    setTranscript("");
    setPhase("listening");
    recognition.start();
  };

  const speak = (text: string) => {
    if (!isVoiceActive()) return;
    const utterance = new SpeechSynthesisUtterance(text.replaceAll("**", ""));
    utterance.lang = answerLanguage;
    utterance.onend = () => listen();
    setPhase("speaking");
    window.speechSynthesis.speak(utterance);
  };

  // Read Leo's answer out and listen again; a failed or stopped reply goes straight back to listening.
  const handleReply = (reply: LeoMessage | undefined) => {
    const answer = reply?.status === "done" ? reply.content : "";
    if (answer) speak(answer);
    else listen();
  };

  const start = () => {
    // Voice mode always opens; when the microphone can't be used, the screen explains why instead.
    if (!window.isSecureContext) {
      setUnavailableReason(t("voice.needsHttps"));
      setPhase("unavailable");
      return;
    }
    if (!getRecognitionConstructor() || !("speechSynthesis" in window)) {
      setUnavailableReason(t("voice.unsupported"));
      setPhase("unavailable");
      return;
    }
    activeRef.current = true;
    mutedRef.current = false;
    setMuted(false);
    listen();
  };

  const end = () => {
    activeRef.current = false;
    stopListening();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setTranscript("");
    setPhase("off");
  };

  const toggleMute = () => {
    const next = !mutedRef.current;
    mutedRef.current = next;
    setMuted(next);
    if (next) stopListening();
    else if (phase === "listening") listen();
  };

  // listen() is a no-op once voice mode has ended.

  React.useEffect(
    () => () => {
      activeRef.current = false;
      recognitionRef.current?.abort();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    },
    [],
  );

  return { phase, transcript, muted, unavailableReason, start, end, toggleMute, isActive: phase !== "off" };
}
