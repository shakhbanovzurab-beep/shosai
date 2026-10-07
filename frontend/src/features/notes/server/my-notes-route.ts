import { NextResponse } from "next/server";

import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import { findMeetingNote } from "../data/meeting-notes";
import { MY_NOTES_MAX_CHARS, type MyNotesResponse } from "../domain/manual-notes";
import { getMyNotes, saveMyNotes } from "./demo-my-notes";
import { refuse } from "./problems";

type Context = { params: Promise<{ id: string }> };

const bodySchema = z.object({ text: z.string().max(MY_NOTES_MAX_CHARS) });
const backendPath = (id: string) => `/v1/notes/${encodeURIComponent(id)}/my-notes`;

/** /api/notes/:id/my-notes: the user's own notes on a meeting. */
export const myNotesRoute = {
  async GET(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, backendPath(id));
    if (upstream) return upstream;
    if (!findMeetingNote(id)) return refuse("meetingNotFound", 404);
    return NextResponse.json<MyNotesResponse>({ notes: getMyNotes(id) });
  },

  async PUT(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, backendPath(id));
    if (upstream) return upstream;
    if (!findMeetingNote(id)) return refuse("meetingNotFound", 404);
    const body = bodySchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse("notesTooLong", 422);
    return NextResponse.json<MyNotesResponse>({ notes: saveMyNotes(id, body.data.text) });
  },
};
