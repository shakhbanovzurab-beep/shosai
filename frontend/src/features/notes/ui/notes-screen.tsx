import { meetingNotes } from "../data/meeting-notes";
import { groupNotesByRecency } from "../domain/format";
import type { NotesView } from "../domain/notes-href";
import { NotesLibrary } from "./notes-library";

interface NotesScreenProps {
  readonly activeFolderId: string | undefined;
  readonly view: NotesView;
}

/** The Notes library with the sample meetings, grouped by recency on the server. */
export function NotesScreen({ activeFolderId, view }: NotesScreenProps) {
  return <NotesLibrary groups={groupNotesByRecency(meetingNotes)} activeFolderId={activeFolderId} view={view} />;
}
