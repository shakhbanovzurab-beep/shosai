import type { ManualNotes } from "./types";

/** Longest Markdown the user's own notes may be, so one meeting can't fill the store. */
export const MY_NOTES_MAX_CHARS = 50_000;

/** GET and PUT /api/notes/:id/my-notes; null before the user has written anything. */
export interface MyNotesResponse {
  notes: ManualNotes | null;
}
