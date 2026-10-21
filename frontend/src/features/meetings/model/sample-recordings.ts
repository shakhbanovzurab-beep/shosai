import { addMinutes } from "date-fns";

import { meetingNotes } from "@/features/notes/data/meeting-notes";
import type { MeetingNote } from "@/features/notes/domain/types";

import { NOTE_SOURCES } from "../data/demo-meetings";
import type { Meeting } from "../domain/meeting";

/*
 * Образцы записей «Заметок» для раздела на моках разработки: у «Заметок» уже есть API, а моков нет (F2-D1).
 * Модуль грузится динамически и только на моках, поэтому в сборку образцы не попадают.
 */

function fromNote(note: MeetingNote): Meeting {
  const source = NOTE_SOURCES[note.id] ?? "google_meet";
  return {
    id: `note-${note.id}`,
    title: note.title,
    start: note.startedAt,
    end: addMinutes(new Date(note.startedAt), note.durationMinutes).toISOString(),
    source,
    joinUrl: null,
    // Комната, как её назвало приглашение: данные, как и название, а не текст интерфейса.
    location: source === "in_person" ? "Office" : null,
    participants: note.participants.map(({ name }) => ({ name })),
    recap: { noteId: note.id, summary: note.summary, tasks: note.actionItems.length, decisions: note.decisions.length },
    recording: { noteId: note.id, live: false, busy: false },
  };
}

export const sampleRecordings = (): Meeting[] => meetingNotes.map(fromNote);
