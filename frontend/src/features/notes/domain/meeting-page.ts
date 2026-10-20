import type { MeetingCard } from "./library";

/** Человек встречи: добавленный вручную, из календаря или узнанный по голосу. */
export interface MeetingParticipant {
  id: string;
  name: string | null;
  email: string | null;
  /** Только добавленного вручную можно убрать. */
  source: string;
}

/** Голос записи: его номер, роль (владелец или нумерованный) и сколько он говорил. */
export interface MeetingSpeaker {
  idx: number;
  role: string;
  talkMs: number;
}

/** Встреча, какой её показывает её страница: карточка и то, что видно только на странице. */
export interface MeetingPage extends MeetingCard {
  /** Может ли человек менять встречу: участников, шаблон, запись Leo. */
  manageable: boolean;
  templateId: string | null;
  lineCount: number;
  revision: number;
  /** Последний прогон встречи: по нему видно, что записи обновились с голосами. */
  runId: string | null;
  participants: MeetingParticipant[];
  speakers: MeetingSpeaker[];
}

/** Чей голос у реплики: владельца встречи, нумерованного спикера или неизвестно. */
export type Voice = { kind: "owner" } | { kind: "number"; n: number } | { kind: "unknown" };

/** У живой встречи без разметки голос владельца — сторона «я» (0); у записи — голос с ролью владельца. */
const LIVE_OWNER = 0;

export function voiceOf(idx: number | null, speakers: readonly MeetingSpeaker[]): Voice {
  if (idx === null) return { kind: "unknown" };
  const owner = speakers.length === 0 ? LIVE_OWNER : speakers.find((speaker) => speaker.role === "owner")?.idx;
  return idx === owner ? { kind: "owner" } : { kind: "number", n: idx + 1 };
}
