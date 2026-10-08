import type { TaskStatus, TranscriptLine } from "../domain/content-contract";
import type { MeetingSeed } from "./types";

/*
 * Builders for the demo meetings' rows. Titles, summaries, action items and transcripts are what members
 * said and wrote in their meetings, so they stay as written in every interface language.
 */

type ActionSeed = MeetingSeed["actions"][number];

/** An action item from a meeting: what, whose (by name), its status and its due day relative to today. */
export const action = (text: string, owner: string | null, status: TaskStatus, dueIn: number | null): ActionSeed => ({
  text,
  owner,
  status,
  dueIn,
});

/** A line of a transcript: who said it, seconds into the meeting, and what they said. */
export const said = (speaker: string, at: number, text: string): TranscriptLine => ({ speaker, at, text });
