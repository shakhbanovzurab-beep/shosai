"use client";

import { AnimatePresence, m } from "framer-motion";
import { ArrowUp, AudioLines, Square } from "lucide-react";
import { useTranslations } from "next-intl";

import { InputGroupButton } from "@/components/ui/input-group";

export type ComposerAction = "stop" | "send" | "voice";

type LeoComposerActionProps = {
  readonly action: ComposerAction;
  readonly canSend: boolean;
  readonly onStop: () => void;
  readonly onStartVoice: () => void;
};

/** The composer's one round button — Stop, Send or Voice mode — swapping with a quick scale. */
export function LeoComposerAction({ action, canSend, onStop, onStartVoice }: LeoComposerActionProps) {
  const t = useTranslations("leo");
  return (
    <div className="flex">
      <AnimatePresence mode="popLayout" initial={false}>
        <m.span
          key={action}
          className="flex"
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.6 }}
          transition={{ duration: 0.15 }}
        >
          {action === "stop" ? (
            <InputGroupButton
              type="button"
              variant="default"
              size="icon-sm"
              className="rounded-full"
              aria-label={t("composer.stop")}
              onClick={onStop}
            >
              <Square className="fill-current" />
            </InputGroupButton>
          ) : null}
          {action === "send" ? (
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              className="rounded-full"
              disabled={!canSend}
              aria-label={t("composer.send")}
            >
              <ArrowUp />
            </InputGroupButton>
          ) : null}
          {action === "voice" ? (
            <InputGroupButton
              type="button"
              variant="default"
              size="icon-sm"
              className="rounded-full"
              aria-label={t("composer.startVoice")}
              title={t("composer.voiceMode")}
              onClick={onStartVoice}
            >
              <AudioLines />
            </InputGroupButton>
          ) : null}
        </m.span>
      </AnimatePresence>
    </div>
  );
}
