import type { CountsOut, FolderOut, MeetingCardOut } from "../api/notes-api";
import type { LibraryCounts, MeetingCard } from "../domain/library";
import type { NoteFolder } from "../domain/types";

/** Карточка библиотеки из ответа сервера. */
export function cardOf(out: MeetingCardOut): MeetingCard {
  return {
    id: out.id,
    title: out.title,
    status: out.status,
    source: out.source,
    startedAt: out.started_at,
    durationMinutes: Math.round(out.seconds / 60),
    owned: out.owned,
    folderId: out.folder_id ?? undefined,
    participantNames: out.participant_names,
    participantCount: out.participant_count,
    summary: out.summary,
    keyPoints: out.key_points,
    firstDecision: out.first_decision,
    actionItems: out.action_items,
    notes: out.notes,
  };
}

export const folderOf = (out: FolderOut): NoteFolder => ({ id: out.id, name: out.name, color: out.color });

export const countsOf = (out: CountsOut): LibraryCounts => ({
  all: out.all,
  byFolder: new Map(out.folders.map((folder) => [folder.folder_id, folder.count])),
});
