"use client";

import dynamic from "next/dynamic";

import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutosave } from "@/hooks/use-autosave";

import type { ManualNotes } from "../domain/types";
import { reportSaveFailure, retryMyNotes, saveMyNotes, useMyNotes } from "../model/my-notes";

const EditorSkeleton = () => (
  <div className="flex flex-col gap-3" aria-busy="true">
    <Skeleton className="h-5 w-40" />
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-4/5" />
    <Skeleton className="h-4 w-2/3" />
  </div>
);

// The editor is the heaviest part of the page, so it loads only once the Notes tab needs it.
const NotesEditor = dynamic(() => import("./notes-editor").then((module) => module.NotesEditor), {
  ssr: false,
  loading: EditorSkeleton,
});

function MyNotesEditor({ noteId, notes }: { noteId: string; notes: ManualNotes | null }) {
  const t = useTranslations("notesNote");
  const common = useTranslations("common");
  // Saves quietly as the user types; only a failed save speaks up (a toast with Retry).
  const autosave = useAutosave(
    (text) => saveMyNotes(noteId, text),
    800,
    (retry, error) => reportSaveFailure(noteId, retry, error, t, common),
  );
  return <NotesEditor initialMarkdown={notes?.text ?? ""} onChange={autosave.schedule} onFlush={autosave.flush} />;
}

/** The Notes tab: the user’s own notes, from the desktop app or written here, edited in place and saved as typed. */
export function MyNotes({ noteId }: { readonly noteId: string }) {
  const t = useTranslations("notesNote");
  const state = useMyNotes(noteId);
  if (state.status === "loading") return <EditorSkeleton />;
  if (state.status === "error")
    return (
      <LoadError title={t("myNotes.loadFailed")} message={state.message} onRetry={() => void retryMyNotes(noteId)} />
    );
  return <MyNotesEditor noteId={noteId} notes={state.data.notes} />;
}
