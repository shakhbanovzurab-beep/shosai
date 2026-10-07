"use client";

import * as React from "react";

import { cn } from "cn";
import { AnimatePresence, m } from "framer-motion";
import { Maximize, Minimize, Paperclip, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { ThinkingOrb } from "thinking-orbs";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useVoiceModeEnabled } from "@/features/settings";

import { useLeoAttachments } from "../model/use-leo-attachments";
import type { useLeoChat } from "../model/use-leo-chat";
import { useLeoVoice } from "../model/use-leo-voice";
import { LeoComposer } from "./leo-composer";
import { LeoEmptyState } from "./leo-empty-state";
import { LeoMessageList } from "./leo-message-list";
import type { LeoPlace } from "./leo-place";
import { LeoVoiceMode } from "./leo-voice-mode";

interface LeoPanelProps {
  readonly chat: ReturnType<typeof useLeoChat>;
  /** Where Leo works ("Personal", "In Lumen"), what it can see there, and what bounds it. */
  readonly place: LeoPlace;
  readonly pathname: string;
  readonly expanded: boolean;
  readonly onToggleExpanded: () => void;
  readonly onCollapse: () => void;
  readonly onClose: () => void;
}

export function LeoPanel({ chat, place, pathname, expanded, onToggleExpanded, onCollapse, onClose }: LeoPanelProps) {
  const t = useTranslations("leo");
  const { messages, isBusy, send, stop, regenerate, editLast, reset } = chat;
  const attachments = useLeoAttachments();
  const voice = useLeoVoice({ onSend: send });
  const voiceEnabled = useVoiceModeEnabled();

  // Switching Voice mode off in Settings mid-conversation hangs up, so the microphone stops listening.
  React.useEffect(() => {
    if (!voiceEnabled && voice.isActive) voice.end();
  }, [voiceEnabled, voice.isActive, voice.end]);
  const [isDragging, setIsDragging] = React.useState(false);
  const dragDepth = React.useRef(0);

  const hasFiles = (event: React.DragEvent) => event.dataTransfer.types.includes("Files");

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
      onDragEnter={(event) => {
        if (!hasFiles(event)) return;
        dragDepth.current += 1;
        setIsDragging(true);
      }}
      onDragLeave={(event) => {
        if (!hasFiles(event)) return;
        dragDepth.current -= 1;
        if (dragDepth.current === 0) setIsDragging(false);
      }}
      onDragOver={(event) => {
        if (hasFiles(event)) event.preventDefault();
      }}
      onDrop={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        dragDepth.current = 0;
        setIsDragging(false);
        attachments.addFiles(event.dataTransfer.files);
      }}
      className={cn(
        "group/leo relative flex w-[calc(100vw-2rem)] flex-col overflow-hidden border bg-background shadow-2xl",
        expanded
          ? "h-dvh w-screen border-transparent shadow-none sm:w-screen"
          : "h-[min(38rem,calc(100dvh-7rem))] sm:w-[25rem]",
      )}
    >
      <m.header layout="position" className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-2 py-2.5">
        <div className="flex items-center">
          <HeaderAction label={t("panel.newChat")} onClick={reset} disabled={messages.length === 0}>
            <Plus />
          </HeaderAction>
        </div>
        {/* The orb hangs off the left edge so the title itself sits exactly in the middle. */}
        <div className="relative flex flex-col items-center text-center">
          <span
            className="absolute end-full top-1/2 me-2.5 flex -translate-y-1/2 [&_canvas]:size-8!"
            aria-hidden="true"
          >
            <ThinkingOrb state={isBusy ? "solving" : "breathing"} size={32} />
          </span>
          <h2 className="font-medium text-sm leading-none">Leo</h2>
          <p className="mt-1 whitespace-nowrap text-muted-foreground text-xs leading-none">
            {isBusy ? t("panel.working") : place.label}
          </p>
        </div>
        <div className="flex items-center justify-end gap-0.5">
          <HeaderAction label={expanded ? t("panel.exitFullScreen") : t("panel.fullScreen")} onClick={onToggleExpanded}>
            <AnimatePresence mode="popLayout" initial={false}>
              <m.span
                key={expanded ? "minimize" : "maximize"}
                className="flex"
                initial={{ opacity: 0, rotate: -90, scale: 0.5 }}
                animate={{ opacity: 1, rotate: 0, scale: 1 }}
                exit={{ opacity: 0, rotate: 90, scale: 0.5 }}
                transition={{ duration: 0.2 }}
              >
                {expanded ? <Minimize /> : <Maximize />}
              </m.span>
            </AnimatePresence>
          </HeaderAction>
          <HeaderAction label={t("panel.close")} onClick={onClose}>
            <X />
          </HeaderAction>
        </div>
      </m.header>
      <Separator />

      {voice.isActive && voiceEnabled ? (
        <LeoVoiceMode voice={voice} />
      ) : (
        <>
          <m.div layout="position" className="flex min-h-0 flex-1 flex-col">
            {messages.length === 0 ? (
              <LeoEmptyState pathname={pathname} scope={place.scope} notice={place.notice} onSelect={send} />
            ) : (
              <LeoMessageList messages={messages} isBusy={isBusy} onRegenerate={regenerate} onEditLast={editLast} />
            )}
          </m.div>

          <m.div layout="position">
            <LeoComposer
              caption={place.caption}
              isBusy={isBusy}
              attachments={attachments}
              onSend={send}
              onStop={stop}
              onStartVoice={voice.start}
              voiceEnabled={voiceEnabled}
            />
          </m.div>
        </>
      )}

      {isDragging && (
        <div className="pointer-events-none absolute inset-2 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-primary border-dashed bg-background/90 text-sm">
          <Paperclip className="size-5" />
          {t("panel.dropFiles")}
        </div>
      )}
    </m.section>
  );
}

function HeaderAction({
  label,
  className,
  ...props
}: React.ComponentProps<typeof Button> & { readonly label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          className={cn("text-muted-foreground", className)}
          {...props}
        />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
