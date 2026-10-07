import type { NotesView } from "./notes-href";
import type { NoteFolder, NoteGroup } from "./types";

/** What the library shows for the current folder: counts, the grid's featured meeting and the groups. */
export function deriveLibrary(
  groups: NoteGroup[],
  folders: NoteFolder[],
  requestedFolderId: string | undefined,
  view: NotesView,
) {
  const foldersById = new Map(folders.map((folder) => [folder.id, folder]));
  // A deleted or unknown folder in the URL falls back to all meetings.
  const activeFolderId = requestedFolderId && foldersById.has(requestedFolderId) ? requestedFolderId : undefined;
  const allNotes = groups.flatMap((group) => group.items);

  const countByFolder = new Map<string, number>();
  for (const note of allNotes) {
    if (note.folderId) countByFolder.set(note.folderId, (countByFolder.get(note.folderId) ?? 0) + 1);
  }

  const filtered = groups
    .map((group) => ({ ...group, items: group.items.filter((n) => !activeFolderId || n.folderId === activeFolderId) }))
    .filter((group) => group.items.length > 0);

  // Only the grid on "All meetings" gives the newest meeting a large card of its own.
  const featured = activeFolderId || view !== "grid" ? undefined : filtered.at(0)?.items.at(0);
  const visibleGroups = filtered
    .map((group) => ({ ...group, items: group.items.filter((n) => n !== featured) }))
    .filter((group) => group.items.length > 0);

  return { foldersById, activeFolderId, allNotes, countByFolder, featured, visibleGroups };
}
