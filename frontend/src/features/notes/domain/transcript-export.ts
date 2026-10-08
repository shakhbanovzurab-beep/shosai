import { formatTimestamp } from "./format";
import { transcriptCues } from "./transcript-cues";
import type { MeetingNote } from "./types";

/** The formats a transcript downloads in; the UI names each one in the interface language. */
export const EXPORT_FORMATS = ["txt", "md", "srt", "vtt", "json"] as const;
export type ExportFormat = (typeof EXPORT_FORMATS)[number];

export const EXPORT_MIME_TYPES: Record<ExportFormat, string> = {
  txt: "text/plain",
  md: "text/markdown",
  srt: "application/x-subrip",
  vtt: "text/vtt",
  json: "application/json",
};

/** 95 → "00:01:35,000" (SubRip) or "00:01:35.000" (WebVTT). */
function cueClock(seconds: number, separator: "," | ".") {
  const whole = Math.floor(seconds);
  const parts = [Math.floor(whole / 3600), Math.floor((whole % 3600) / 60), whole % 60];
  const millis = Math.round((seconds - whole) * 1000);
  return `${parts.map((part) => String(part).padStart(2, "0")).join(":")}${separator}${String(millis).padStart(3, "0")}`;
}

/** WebVTT cue text may not hold raw "&", "<" or ">". */
const VTT_ENTITIES: Readonly<Record<string, string>> = { "&": "&amp;", "<": "&lt;", ">": "&gt;" };
const vttEscape = (text: string) => text.replace(/[&<>]/g, (character) => VTT_ENTITIES[character] ?? character);

/**
 * The transcript as a file's contents in the given format. What was said stays as said; `heading` (the date
 * and length of the meeting) comes worded in the interface language, for the text and Markdown files.
 */
export function exportTranscript(note: MeetingNote, format: ExportFormat, heading: string): string {
  switch (format) {
    case "txt":
      return [
        note.title,
        heading,
        "",
        ...note.transcript.map((line) => `[${formatTimestamp(line.at)}] ${line.speaker}: ${line.text}`),
      ].join("\n");
    case "md":
      return [
        `# ${note.title}`,
        "",
        `_${heading}_`,
        "",
        ...note.transcript.map((line) => `**${line.speaker}** · ${formatTimestamp(line.at)}  \n${line.text}\n`),
      ].join("\n");
    case "srt":
      return transcriptCues(note)
        .map((cue, index) =>
          [
            index + 1,
            `${cueClock(cue.start, ",")} --> ${cueClock(cue.end, ",")}`,
            `${cue.speaker}: ${cue.text}`,
            "",
          ].join("\n"),
        )
        .join("\n");
    case "vtt":
      return [
        "WEBVTT",
        "",
        ...transcriptCues(note).map(
          (cue) =>
            `${cueClock(cue.start, ".")} --> ${cueClock(cue.end, ".")}\n<v ${vttEscape(cue.speaker)}>${vttEscape(cue.text)}\n`,
        ),
      ].join("\n");
    case "json":
      return JSON.stringify(
        {
          title: note.title,
          startedAt: note.startedAt,
          durationMinutes: note.durationMinutes,
          participants: note.participants.map(({ name, role }) => ({ name, role })),
          transcript: transcriptCues(note),
        },
        null,
        2,
      );
  }
}

export const exportFileName = (note: MeetingNote, format: ExportFormat) => `${note.id}-transcript.${format}`;
