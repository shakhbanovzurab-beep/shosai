import { groupNotesByRecency } from "./format";
import type { MeetingCard } from "./library";
import type { NotesView } from "./notes-href";
import type { NoteFolder } from "./types";

/**
 * Что библиотека показывает для текущей папки: группы по давности и крупную карточку сетки. Папку отбирает
 * сервер; неизвестная или удалённая папка в адресе показывает все встречи.
 */
export function activeFolderOf(folders: readonly NoteFolder[] | null, requested: string | undefined) {
  if (!requested) return undefined;
  // Пока папки не прочитаны, верим адресу: сервер сам покажет пустую папку, если её нет.
  if (folders === null) return requested;
  return folders.some((folder) => folder.id === requested) ? requested : undefined;
}

/** Крупная карточка «последней встречи» есть только у сетки «Всех встреч». */
export const hasFeaturedSlot = (activeFolderId: string | undefined, view: NotesView) =>
  activeFolderId === undefined && view === "grid";

/**
 * `slotTaken` — крупную карточку уже заняла загружаемая запись: самая новая встреча тогда идёт в группы, а когда
 * запись станет встречей, та сама займёт слот, и сетка под ним не сдвинется.
 */
export function deriveLibrary(
  items: readonly MeetingCard[],
  activeFolderId: string | undefined,
  view: NotesView,
  zone: string,
  slotTaken = false,
) {
  const featured = hasFeaturedSlot(activeFolderId, view) && !slotTaken ? items.at(0) : undefined;
  const rest = featured ? items.slice(1) : items;
  return { featured, groups: groupNotesByRecency(rest, zone) };
}
