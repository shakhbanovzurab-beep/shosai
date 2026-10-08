import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { findMeetingNote } from "../data/meeting-notes";
import { MY_NOTES_MAX_CHARS, type MyNotesResponse } from "../domain/manual-notes";
import { getMyNotes, saveMyNotes } from "./demo-my-notes";
import { refuse } from "./problems";

type Context = { params: Promise<{ id: string }> };

const bodySchema = z.object({ text: z.string().max(MY_NOTES_MAX_CHARS) });

/** /api/notes/:id/my-notes: the user's own notes on a meeting. */
export const myNotesRoute = {
  async GET(_request: Request, { params }: Context) {
    const { id } = await params;
    if (!findMeetingNote(id)) return refuse("meetingNotFound", 404);
    return JsonResponse.json<MyNotesResponse>({ notes: getMyNotes(id) });
  },

  async PUT(request: Request, { params }: Context) {
    const { id } = await params;
    if (!findMeetingNote(id)) return refuse("meetingNotFound", 404);
    const body = bodySchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse("notesTooLong", 422);
    return JsonResponse.json<MyNotesResponse>({ notes: saveMyNotes(id, body.data.text) });
  },
};
