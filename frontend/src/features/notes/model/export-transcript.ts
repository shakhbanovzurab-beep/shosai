import { notesApi } from "../api/notes-api";
import type { MeetingPage, Voice } from "../domain/meeting-page";
import { EXPORT_MIME_TYPES, type ExportFormat, exportFileName, exportTranscript } from "../domain/transcript-export";
import type { TranscriptDocument, TranscriptLine } from "../domain/types";
import { transcriptForExport, transcriptLinesOf } from "./meeting-content";
import { pageOf } from "./meeting-resource";

/** Встреча и её реплики как выгружаемый документ: люди — по именам, а без имени — по адресу. */
export const documentOf = (page: MeetingPage, transcript: TranscriptLine[]): TranscriptDocument => ({
  id: page.id,
  title: page.title,
  startedAt: page.startedAt,
  durationMinutes: page.durationMinutes,
  participants: page.participants.map((person) => ({ name: person.name ?? person.email ?? "", role: "" })),
  transcript,
});

/** Документ встречи, которая не открыта (выгрузка из библиотеки): её голоса и расшифровка читаются свежими. */
export async function transcriptDocument(
  id: string,
  voiceName: (owned: boolean) => (voice: Voice) => string,
): Promise<TranscriptDocument> {
  const [meeting, lines] = await Promise.all([notesApi.meeting(id), transcriptForExport(id)]);
  const page = pageOf(meeting);
  return documentOf(page, transcriptLinesOf(lines, page.speakers, voiceName(page.owned)));
}

/**
 * Saves the transcript as a file named after the meeting, in the chosen format. `heading` is the meeting's
 * date and length in the interface language; the lines themselves stay as they were said.
 */
export function downloadTranscript(note: TranscriptDocument, format: ExportFormat, heading: string) {
  const type = `${EXPORT_MIME_TYPES[format]};charset=utf-8`;
  const url = URL.createObjectURL(new Blob([exportTranscript(note, format, heading)], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = exportFileName(note, format);
  link.click();
  URL.revokeObjectURL(url);
}
