"use client";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import type { MeetingPage } from "../domain/meeting-page";
import { retryMindMap, retryTranscript, transcriptLinesOf, useMindMap, useTranscript } from "../model/meeting-content";
import { NoteMindMap } from "./note-mind-map";
import { SpeakerStats } from "./speaker-stats";
import { TranscriptSearch } from "./transcript-search";
import { useVoiceName } from "./use-voice-name";

// Каркас вкладки, пока её данные едут: несколько строк, как у реплик.
function PanelSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-busy="true">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="flex gap-3">
          <Skeleton className="size-6 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-4 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Вкладка расшифровки: вся встреча, кто сколько говорил и поиск по репликам. */
export function TranscriptPanel({ note, moment }: { readonly note: MeetingPage; readonly moment?: number }) {
  const t = useTranslations("notesNote");
  const state = useTranscript(note.id);
  const voiceName = useVoiceName();
  if (state.status === "loading") return <PanelSkeleton />;
  if (state.status === "error")
    return (
      <LoadError
        title={t("transcript.loadFailed")}
        message={state.message}
        onRetry={() => void retryTranscript(note.id)}
      />
    );
  if (state.data.length === 0) return <p className="text-muted-foreground text-sm">{t("transcript.empty")}</p>;
  const lines = transcriptLinesOf(state.data, note.speakers, voiceName(note.owned));
  return (
    <div className="flex flex-col gap-6">
      <SpeakerStats note={{ transcript: lines, durationMinutes: note.durationMinutes }} />
      <TranscriptSearch lines={lines} moment={moment} />
    </div>
  );
}

/** Вкладка карты: темы встречи деревом; без записей Leo карты ещё нет. */
export function MindMapPanel({ noteId }: { readonly noteId: string }) {
  const t = useTranslations("notesNote");
  const state = useMindMap(noteId);
  if (state.status === "loading") return <PanelSkeleton />;
  if (state.status === "error")
    return (
      <LoadError title={t("mindMap.loadFailed")} message={state.message} onRetry={() => void retryMindMap(noteId)} />
    );
  if (state.data === null) return <p className="text-muted-foreground text-sm">{t("mindMap.none")}</p>;
  return <NoteMindMap root={state.data} />;
}
