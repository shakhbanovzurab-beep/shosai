import { type AnonymousSpeaker, type ShareLink, speakerLabels } from "./share-link";
import type { MeetingNote, TranscriptLine } from "./types";

/** A meeting as people outside it see it through a share link. */
export interface SharedNote {
  token: string;
  title: string;
  startedAt: string;
  durationMinutes: number;
  /** Names and roles when the link shows names; otherwise only how many people there were. */
  participants: { name: string; role: string }[] | null;
  participantCount: number;
  summary: string;
  keyPoints: string[];
  decisions: string[];
  actionItems: { id: string; text: string; owner: string | null; done: boolean }[];
  /** Null when the link hides the transcript. */
  transcript: TranscriptLine[] | null;
  allowComments: boolean;
}

/**
 * What a link shows of a meeting: no emails ever, names and the transcript only when the link allows.
 * `anonymous` numbers the speakers when names are hidden, in the reader's language.
 */
export function toSharedNote(note: MeetingNote, link: ShareLink, anonymous: AnonymousSpeaker): SharedNote {
  const { showNames, showTranscript, allowComments } = link.settings;
  const labels = speakerLabels(
    note.transcript.map((line) => line.speaker),
    showNames,
    anonymous,
  );
  return {
    token: link.token,
    title: note.title,
    startedAt: note.startedAt,
    durationMinutes: note.durationMinutes,
    participants: showNames ? note.participants.map(({ name, role }) => ({ name, role })) : null,
    participantCount: note.participants.length,
    summary: note.summary,
    keyPoints: note.keyPoints,
    decisions: note.decisions,
    actionItems: note.actionItems.map(({ id, text, owner, done }) => ({
      id,
      text,
      owner: showNames ? owner : null,
      done,
    })),
    transcript: showTranscript
      ? note.transcript.map((line) => ({ ...line, speaker: labels.get(line.speaker) ?? line.speaker }))
      : null,
    allowComments,
  };
}
