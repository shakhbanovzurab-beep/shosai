import { toast } from "sonner";

import { notesApi } from "../api/notes-api";
import { refreshCounts } from "./folders";
import { dropCard, pendingDeletes, refreshLibraries } from "./library-resource";
import { describeNoteError } from "./problem-words";
import type { CommonWords, NotesWords } from "./words";

/**
 * Удаляет встречу с «Отменить»: она сразу уходит из всех списков, а `DELETE` уходит, только когда тост закрылся
 * без отмены. Сервер прячет встречу на 7 дней, поддержка может её вернуть (MT-D8).
 */
export function deleteNote(note: { id: string; title: string }, t: NotesWords, common: CommonWords) {
  let settled = false;
  pendingDeletes.add(note.id);
  dropCard(note.id);
  const commit = () => {
    if (settled) return;
    settled = true;
    notesApi.remove(note.id).then(
      () => {
        pendingDeletes.delete(note.id);
        refreshCounts();
      },
      (error: unknown) => {
        pendingDeletes.delete(note.id);
        toast.error(describeNoteError(error, t));
        refreshLibraries();
      },
    );
  };
  toast(t("deleted", { title: note.title }), {
    action: {
      label: common("actions.undo"),
      onClick: () => {
        settled = true;
        pendingDeletes.delete(note.id);
        refreshLibraries();
      },
    },
    onAutoClose: commit,
    onDismiss: commit,
  });
}
