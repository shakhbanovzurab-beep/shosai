import type { TranscriptDocument } from "./types";

/** A transcript line with when it ends: what subtitles and talk-time figures are built from. */
export interface Cue {
  speaker: string;
  text: string;
  /** Seconds from the start of the recording. */
  start: number;
  end: number;
}

/** About 150 words a minute, a usual speaking rate. */
const WORDS_PER_SECOND = 2.5;
const MIN_CUE_SECONDS = 2;
const WORD = /\S+/g;

/**
 * Lines carry only when they start, so each runs as long as its words take to say, but never past the next
 * line or the end of the meeting. Pauses between lines then count as nobody's talk time.
 */
export function transcriptCues(note: Pick<TranscriptDocument, "transcript" | "durationMinutes">): Cue[] {
  const meetingEnd = note.durationMinutes * 60;
  return note.transcript.map((line, index) => {
    const spoken =
      line.duration ?? Math.max(MIN_CUE_SECONDS, Math.round((line.text.match(WORD)?.length ?? 0) / WORDS_PER_SECOND));
    const limit = note.transcript[index + 1]?.at ?? Math.max(meetingEnd, line.at + spoken);
    return { speaker: line.speaker, text: line.text, start: line.at, end: Math.min(line.at + spoken, limit) };
  });
}
