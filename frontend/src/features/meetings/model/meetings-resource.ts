"use client";

import { addMinutes } from "date-fns";

import { type MeetingNote, meetingNotes } from "@/features/notes";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { demoMeetings, NOTE_SOURCES } from "../data/demo-meetings";
import type { Meeting } from "../domain/meeting";

/** A recording in Notes as a past meeting, with Leo's recap taken from the note. */
function fromNote(note: MeetingNote): Meeting {
  const source = NOTE_SOURCES[note.id] ?? "google_meet";
  return {
    id: `note-${note.id}`,
    title: note.title,
    start: note.startedAt,
    end: addMinutes(new Date(note.startedAt), note.durationMinutes).toISOString(),
    source,
    joinUrl: null,
    // The room as the invitation names it: data, like the title, not interface copy.
    location: source === "in_person" ? "Office" : null,
    participants: note.participants.map(({ name }) => ({ name })),
    recap: { noteId: note.id, summary: note.summary, tasks: note.actionItems.length, decisions: note.decisions.length },
  };
}

/**
 * The meetings list as a client resource: the scheduled sample meetings plus the recordings in Notes,
 * with loading and error states, and the place to swap in `GET /meetings` once the backend has it.
 */
export const meetingsResource = createPollingResource(async () => [...demoMeetings(), ...meetingNotes.map(fromNote)]);

export const useMeetings = () => usePollingResource(meetingsResource);
