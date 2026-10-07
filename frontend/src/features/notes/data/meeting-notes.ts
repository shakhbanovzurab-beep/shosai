import type { MeetingNote, NoteFolder } from "../domain/types";
import { sampleMyNotes } from "./sample-my-notes";
import { hubNotes } from "./sample-notes-hubs";
import { productNotes } from "./sample-notes-product";
import { romashkaNotes } from "./sample-notes-romashka";
import { romashkaLateNotes } from "./sample-notes-romashka-late";
import { teamNotes } from "./sample-notes-team";

export const noteFolders: NoteFolder[] = [
  { id: "goal", name: "Goal", color: "red" },
  { id: "progress", name: "Progress", color: "blue" },
  { id: "work", name: "Work", color: "amber" },
];

/** The demo account's address (the settings slice's demo user): it marks "(me)" among a meeting's attendees. */
export const ACCOUNT_EMAIL = "arham@lumen.so";

// Sample data until meetings are recorded and transcribed for real.
export const meetingNotes: MeetingNote[] = [
  ...productNotes,
  ...teamNotes,
  ...romashkaNotes,
  ...romashkaLateNotes,
  ...hubNotes,
].map((note) => (sampleMyNotes[note.id] ? { ...note, myNotes: sampleMyNotes[note.id] } : note));

export function findMeetingNote(id: string) {
  return meetingNotes.find((n) => n.id === id);
}
