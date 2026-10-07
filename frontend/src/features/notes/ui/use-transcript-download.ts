"use client";

import { useFormatter, useLocale, useTranslations } from "next-intl";

import { formatMeetingDuration } from "../domain/format";
import type { ExportFormat } from "../domain/transcript-export";
import type { MeetingNote } from "../domain/types";
import { downloadTranscript } from "../model/export-transcript";

/**
 * Downloads a meeting's transcript; the file's heading (date and length) is in the interface language, the
 * lines stay as they were said. Also names each format for the export menus.
 */
export function useTranscriptDownload() {
  const t = useTranslations("notes");
  const format = useFormatter();
  const locale = useLocale();

  const download = (note: MeetingNote, as: ExportFormat) => {
    const heading = t("exportHeading", {
      date: format.dateTime(new Date(note.startedAt), "weekdayDateTime"),
      duration: formatMeetingDuration(locale, note.durationMinutes),
    });
    downloadTranscript(note, as, heading);
  };

  return { download, formatName: (as: ExportFormat) => t(`exportFormats.${as}`) };
}
