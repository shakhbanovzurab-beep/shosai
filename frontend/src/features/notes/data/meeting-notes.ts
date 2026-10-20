import type { MeetingNote } from "../domain/types";
import { sampleMyNotes } from "./sample-my-notes";
import { hubNotes } from "./sample-notes-hubs";
import { productNotes } from "./sample-notes-product";
import { romashkaNotes } from "./sample-notes-romashka";
import { romashkaLateNotes } from "./sample-notes-romashka-late";
import { teamNotes } from "./sample-notes-team";

// Образцы встреч для срезов, что ещё не читают встречи через API (хабы, рабочие пространства, обзор встреч),
// и для публичной страницы ссылки до шага 19 плана notes. Экраны заметок их не читают.
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
