import { EXPORT_MIME_TYPES, type ExportFormat, exportFileName, exportTranscript } from "../domain/transcript-export";
import type { MeetingNote } from "../domain/types";

/**
 * Saves the transcript as a file named after the meeting, in the chosen format. `heading` is the meeting's
 * date and length in the interface language; the lines themselves stay as they were said.
 */
export function downloadTranscript(note: MeetingNote, format: ExportFormat, heading: string) {
  const type = `${EXPORT_MIME_TYPES[format]};charset=utf-8`;
  const url = URL.createObjectURL(new Blob([exportTranscript(note, format, heading)], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = exportFileName(note, format);
  link.click();
  URL.revokeObjectURL(url);
}
