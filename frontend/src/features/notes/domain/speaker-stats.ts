import { transcriptCues } from "./transcript-cues";
import type { TranscriptDocument } from "./types";

export interface SpeakerStat {
  speaker: string;
  /** Seconds the speaker held the floor. */
  seconds: number;
  /** Share of all talk time, rounded to whole percent. */
  percent: number;
  /** How many transcript lines are theirs. */
  lines: number;
}

/** Who talked and how much, the biggest share first. */
export function speakerStats(note: Pick<TranscriptDocument, "transcript" | "durationMinutes">): SpeakerStat[] {
  const bySpeaker = new Map<string, { seconds: number; lines: number }>();
  for (const cue of transcriptCues(note)) {
    const stat = bySpeaker.get(cue.speaker) ?? { seconds: 0, lines: 0 };
    stat.seconds += cue.end - cue.start;
    stat.lines += 1;
    bySpeaker.set(cue.speaker, stat);
  }
  const total = [...bySpeaker.values()].reduce((sum, stat) => sum + stat.seconds, 0);
  return [...bySpeaker]
    .map(([speaker, stat]) => ({ speaker, ...stat, percent: total ? Math.round((stat.seconds / total) * 100) : 0 }))
    .toSorted((a, b) => b.seconds - a.seconds);
}
