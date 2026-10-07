import { type MeetingNote, sampleMeetingNotes } from "@/features/notes/server";

import type { Evidence } from "../domain/contract";
import type { Said } from "./types";

/* The demo's meetings are the recordings in Notes: titles, dates and quotes are read from there. */

const byId = new Map<string, MeetingNote>(sampleMeetingNotes.map((note) => [note.id, note]));

export const sessionOf = (id: string) => byId.get(id) ?? null;

export const sessionStart = (id: string) => byId.get(id)?.startedAt ?? null;

/** A calendar series, by the recurring title ("Romashka weekly sync"); a person's correction applies to all of it. */
export const seriesOf = (id: string) => byId.get(id)?.title ?? id;

/** The line of a recording a fact points at, as evidence; null when the recording or the line is gone. */
export function evidenceOf(said: Said): Evidence | null {
  const note = byId.get(said.note);
  const line = note?.transcript.find((l) => l.at === said.at);
  if (!note || !line) return null;
  return {
    sessionId: note.id,
    meetingTitle: note.title,
    meetingStartedAt: note.startedAt,
    speaker: line.speaker || null,
    startMs: line.at * 1000,
    quote: line.text.replace(/[.!]$/, ""),
  };
}

/** When something said happened: the start of its meeting. */
export const saidAt = (said: Said) => sessionStart(said.note);

/** Sessions in time order, oldest first; unknown ids are dropped. */
export const chronological = (ids: Iterable<string>) =>
  [...ids].filter((id) => byId.has(id)).sort((a, b) => (sessionStart(a) ?? "").localeCompare(sessionStart(b) ?? ""));
