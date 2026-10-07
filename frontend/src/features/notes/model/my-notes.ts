"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { errorMessage } from "@/lib/errors";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { notesApi } from "../api/notes-api";
import type { MyNotesResponse } from "../domain/manual-notes";
import type { CommonWords, NoteWords } from "./words";

// One resource per meeting, made on first use and kept, so going back to a note shows its notes at once.
const resources = new Map<string, PollingResource<MyNotesResponse>>();

function myNotesOf(noteId: string) {
  let resource = resources.get(noteId);
  if (!resource) {
    resource = createPollingResource(() => notesApi.getMyNotes(noteId));
    resources.set(noteId, resource);
  }
  return resource;
}

export const useMyNotes = (noteId: string) => usePollingResource(myNotesOf(noteId));
export const retryMyNotes = (noteId: string) => myNotesOf(noteId).refresh();

/** The editor's autosave: rejects on failure, so the autosave keeps the text for a retry. */
export async function saveMyNotes(noteId: string, text: string) {
  const saved = await notesApi.saveMyNotes(noteId, text);
  myNotesOf(noteId).update(() => saved);
}

/** The editor shows no save status, so a failed save is the one thing it reports: a toast with Retry. */
export function reportSaveFailure(
  noteId: string,
  retry: () => void,
  error: unknown,
  t: NoteWords,
  common: CommonWords,
) {
  toast.error(t("myNotes.saveFailed"), {
    id: `my-notes-${noteId}`,
    description: errorMessage(error),
    action: { label: common("actions.retry"), onClick: retry },
  });
}
