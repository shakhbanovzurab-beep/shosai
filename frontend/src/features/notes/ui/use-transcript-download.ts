"use client";

import { toast } from "sonner";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { formatMeetingDuration } from "../domain/format";
import type { ExportFormat } from "../domain/transcript-export";
import type { TranscriptDocument } from "../domain/types";
import { downloadTranscript, transcriptDocument } from "../model/export-transcript";
import { describeNoteError } from "../model/problem-words";
import { useVoiceName } from "./use-voice-name";

/**
 * Downloads a meeting's transcript; the file's heading (date and length) is in the interface language, the
 * lines stay as they were said. Also names each format for the export menus.
 */
export function useTranscriptDownload() {
  const t = useTranslations("notes");
  const format = useFormatter();
  const locale = useLocale();
  const voiceName = useVoiceName();

  const download = (note: TranscriptDocument, as: ExportFormat) => {
    const heading = t("exportHeading", {
      date: format.dateTime(new Date(note.startedAt), "weekdayDateTime"),
      duration: formatMeetingDuration(locale, note.durationMinutes),
    });
    downloadTranscript(note, as, heading);
  };

  /** Из библиотеки: встреча не открыта, поэтому её расшифровка сначала дочитывается с сервера. */
  const downloadById = async (id: string, as: ExportFormat) => {
    try {
      download(await transcriptDocument(id, voiceName), as);
    } catch (error) {
      toast.error(describeNoteError(error, t));
    }
  };

  return { download, downloadById, formatName: (as: ExportFormat) => t(`exportFormats.${as}`) };
}
