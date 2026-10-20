import { toast } from "sonner";

import { contentApi } from "../api/note-content-api";
import type { MeetingParticipant } from "../domain/meeting-page";
import { patchMeeting } from "./meeting-resource";
import { describeNoteError } from "./problem-words";
import type { NotesWords, NoteWords } from "./words";

type Words = { readonly t: NoteWords; readonly notes: NotesWords };

/** Добавляет человека во встречу по адресу; false, если сервер отказал (причина — в тосте). */
export async function addParticipant(meetingId: string, email: string, { t, notes }: Words): Promise<boolean> {
  try {
    const out = await contentApi.addParticipant(meetingId, email);
    const added: MeetingParticipant = { id: out.id, name: out.name, email: out.email, source: out.source };
    patchMeeting(meetingId, (page) => ({
      ...page,
      participants: [...page.participants, added],
      participantCount: page.participantCount + 1,
    }));
    toast.success(t("participants.added", { email }));
    return true;
  } catch (error) {
    toast.error(describeNoteError(error, notes));
    return false;
  }
}

/** Убирает добавленного вручную; страница меняется сразу, сбой возвращает его обратно. */
export async function removeParticipant(meetingId: string, person: MeetingParticipant, { notes }: Words) {
  patchMeeting(meetingId, (page) => ({
    ...page,
    participants: page.participants.filter((p) => p.id !== person.id),
    participantCount: Math.max(0, page.participantCount - 1),
  }));
  try {
    await contentApi.removeParticipant(meetingId, person.id);
  } catch (error) {
    toast.error(describeNoteError(error, notes));
    patchMeeting(meetingId, (page) => ({
      ...page,
      participants: [...page.participants, person],
      participantCount: page.participantCount + 1,
    }));
  }
}
