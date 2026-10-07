import type { ManualNotes, MeetingNote, MindMapNode, NoteActionItem, NotesApp, TranscriptLine } from "../domain/types";

/*
 * Builders for the demo meetings. Titles, summaries, transcripts, action items, mind maps and the user's own
 * notes are what the meeting's people said and wrote, and what Leo wrote from it, so they stay as written in
 * every interface language.
 */

/** A recorded meeting: its id and title, then everything else it has. */
export const meeting = (id: string, title: string, fields: Omit<MeetingNote, "id" | "title">): MeetingNote => ({
  id,
  title,
  ...fields,
});

/** A transcript line: who said it, how many seconds into the recording, and what they said. */
export const said = (speaker: string, at: number, text: string): TranscriptLine => ({ speaker, at, text });

/** An action item taken from the meeting, open unless `done`. */
export const todo = (id: string, text: string, owner: string, done = false): NoteActionItem => ({
  id,
  text,
  owner,
  done,
});

/** A mind-map topic and the topics under it. */
export const topic = (label: string, ...children: MindMapNode[]): MindMapNode =>
  children.length > 0 ? { label, children } : { label };

/** What the user typed about a meeting in a desktop app, as Markdown. */
export const typed = (app: NotesApp, updatedAt: string, text: string): ManualNotes => ({ app, updatedAt, text });
