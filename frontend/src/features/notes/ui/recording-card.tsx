import { X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { formatBytes } from "@/i18n/format-units";

import type { PendingRecording } from "../domain/types";

interface RecordingCardProps {
  readonly recording: PendingRecording;
  readonly onRemove: (id: string) => void;
}

/** A just-uploaded file: shown right away, waiting for the transcription service. */
export function RecordingCard({ recording, onRemove }: RecordingCardProps) {
  const t = useTranslations("notes");
  const locale = useLocale();
  return (
    <article className="relative flex flex-col gap-4 rounded-2xl border border-dashed bg-card/50 p-5">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2 py-0.5 font-medium text-amber-600 text-xs dark:text-amber-400">
          <span className="relative flex size-1.5" aria-hidden="true">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />
            <span className="relative inline-flex size-1.5 rounded-full bg-current" />
          </span>
          {t("recordings.transcribing")}
        </span>
        <Button
          variant="ghost"
          size="icon-xs"
          className="-me-1 text-muted-foreground"
          aria-label={t("remove", { name: recording.name })}
          onClick={() => onRemove(recording.id)}
        >
          <X />
        </Button>
      </div>
      <div className="flex flex-col gap-1.5">
        <h3 dir="auto" className="truncate font-medium text-base leading-snug">
          {recording.name}
        </h3>
        <p className="text-muted-foreground text-sm" role="status">
          {t("recordings.waiting")}
        </p>
      </div>
      <div className="mt-auto flex items-center gap-3">
        <span className="shrink-0 font-mono text-muted-foreground text-xs tabular-nums">
          {formatBytes(locale, recording.size)}
        </span>
      </div>
    </article>
  );
}
