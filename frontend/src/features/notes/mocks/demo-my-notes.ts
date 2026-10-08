import { sampleMyNotes } from "../data/sample-my-notes";
import type { ManualNotes } from "../domain/types";

// In-memory stand-in used when BACKEND_API_URL is unset, seeded with what the desktop apps "synced";
// on globalThis so every route bundle shares it.
const shared = globalThis as typeof globalThis & { notesDemoMyNotes?: Map<string, ManualNotes> };
shared.notesDemoMyNotes ??= new Map(Object.entries(sampleMyNotes));
const store = shared.notesDemoMyNotes;

export const getMyNotes = (noteId: string): ManualNotes | null => store.get(noteId) ?? null;

/** Saves notes edited here on the web. */
export function saveMyNotes(noteId: string, text: string): ManualNotes {
  const notes: ManualNotes = { app: "web", updatedAt: new Date().toISOString(), text };
  store.set(noteId, notes);
  return notes;
}
