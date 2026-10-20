"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { apiErrorDescription } from "@/lib/api/error-description";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { contentApi, type MyNotesOut } from "../api/note-content-api";
import type { MyNotesResponse } from "../domain/manual-notes";
import type { CommonWords, NoteWords } from "./words";

/** Свои заметки человека из ответа сервера: текст, где правились в последний раз и когда. */
const ownNotesOf = (out: MyNotesOut): MyNotesResponse => ({
  notes: out.notes === null ? null : { app: out.notes.client, updatedAt: out.notes.updated_at, text: out.notes.text },
});

// One resource per meeting, made on first use and kept, so going back to a note shows its notes at once.
const resources = new Map<string, PollingResource<MyNotesResponse>>();

function myNotesOf(noteId: string) {
  let resource = resources.get(noteId);
  if (!resource) {
    resource = createPollingResource(async () => ownNotesOf(await contentApi.myNotes(noteId)));
    resources.set(noteId, resource);
  }
  return resource;
}

export const useMyNotes = (noteId: string) => usePollingResource(myNotesOf(noteId));
export const retryMyNotes = (noteId: string) => myNotesOf(noteId).refresh();

/** The editor's autosave: rejects on failure, so the autosave keeps the text for a retry. */
export async function saveMyNotes(noteId: string, text: string) {
  const saved = ownNotesOf(await contentApi.saveMyNotes(noteId, text));
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
    description: apiErrorDescription(error),
    action: { label: common("actions.retry"), onClick: retry },
  });
}
