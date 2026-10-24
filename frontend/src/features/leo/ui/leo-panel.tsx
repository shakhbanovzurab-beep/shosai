"use client";

import * as React from "react";

import { cn } from "cn";
import { m } from "framer-motion";
import { Paperclip } from "lucide-react";
import { useTranslations } from "use-intl";

import { Separator } from "@/components/ui/separator";
import { useVoiceModeEnabled } from "@/features/settings/model/leo-settings";

import type { LeoChat } from "../model/leo-chat";
import { useLeoAttachments } from "../model/use-leo-attachments";
import { useLeoVoice } from "../model/use-leo-voice";
import { LeoComposer } from "./leo-composer";
import { LeoConversation } from "./leo-conversation";
import { LeoPanelHeader } from "./leo-panel-header";
import type { LeoPlace } from "./leo-place";
import { LeoVoiceMode } from "./leo-voice-mode";
import { useFileDrop } from "./use-file-drop";

/** Вопрос, пришедший, пока Leo отвечал: он ждёт в поле ввода; новый id — новое поле с этим текстом. */
export type LeoDraft = { id: string; text: string };

interface LeoPanelProps {
  readonly chat: LeoChat;
  readonly draft: LeoDraft | null;
  /** Where Leo works ("Personal", "In Lumen"), what it can see there, and what bounds it. */
  readonly place: LeoPlace;
  readonly pathname: string;
  readonly expanded: boolean;
  readonly onToggleExpanded: () => void;
  readonly onCollapse: () => void;
  readonly onClose: () => void;
}

export function LeoPanel({
  chat,
  draft,
  place,
  pathname,
  expanded,
  onToggleExpanded,
  onCollapse,
  onClose,
}: LeoPanelProps) {
  const t = useTranslations("leo");
  const { messages, isBusy, send, stop, reset } = chat;
  const attachments = useLeoAttachments();
  const voice = useLeoVoice({ onSend: send });
  const voiceEnabled = useVoiceModeEnabled();

  // Switching Voice mode off in Settings mid-conversation hangs up, so the microphone stops listening.
  React.useEffect(() => {
    if (!voiceEnabled && voice.isActive) voice.end();
  }, [voiceEnabled, voice.isActive, voice.end]);
  const drop = useFileDrop(chat.attachments, attachments.addFiles);

  return (
    <m.section
      layout
      // Set through style so the corner radius is scale-corrected and morphs with the window.
      style={{ borderRadius: expanded ? 0 : 16 }}
      id="leo-panel"
      data-expanded={expanded}
      aria-label={t("panel.label")}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        if (expanded) onCollapse();
        else onClose();
      }}
      {...drop.handlers}
      className={cn(
        "group/leo relative flex w-[calc(100vw-2rem)] flex-col overflow-hidden border bg-background shadow-2xl",
        expanded
          ? "h-dvh w-screen border-transparent shadow-none sm:w-screen"
          : "h-[min(38rem,calc(100dvh-7rem))] sm:w-[25rem]",
      )}
    >
      <LeoPanelHeader
        isBusy={isBusy}
        placeLabel={place.label}
        expanded={expanded}
        canReset={messages.length > 0}
        onReset={reset}
        onToggleExpanded={onToggleExpanded}
        onClose={onClose}
      />
      <Separator />

      {voice.isActive && voiceEnabled ? (
        <LeoVoiceMode voice={voice} />
      ) : (
        <>
          <m.div layout="position" className="flex min-h-0 flex-1 flex-col">
            <LeoConversation chat={chat} place={place} pathname={pathname} />
          </m.div>

          <m.div layout="position">
            <LeoComposer
              key={draft?.id ?? "composer"}
              initialValue={draft?.text ?? ""}
              caption={place.caption}
              isBusy={isBusy}
              attachments={chat.attachments ? attachments : null}
              onSend={send}
              onStop={stop}
              onStartVoice={voice.start}
              voiceEnabled={voiceEnabled}
            />
          </m.div>
        </>
      )}

      {drop.isDragging && (
        <div className="pointer-events-none absolute inset-2 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-primary border-dashed bg-background/90 text-sm">
          <Paperclip className="size-5" />
          {t("panel.dropFiles")}
        </div>
      )}
    </m.section>
  );
}
