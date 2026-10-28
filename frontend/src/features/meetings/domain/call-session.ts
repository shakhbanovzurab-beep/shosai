import type { CallPerson, CallRole } from "./call";
import type { ChatMessage } from "./chat-log";
import type { CallEnd } from "./join";
import type { Reaction, ShownReaction } from "./reactions";

/* Сессия звонка, какой её видит экран: на моках — демо (data/demo-call), на API — LiveKit (A10). */

export type CallStatus = "connecting" | "connected" | "reconnecting" | "ended";
export type CallMarks = { notes: boolean; recording: boolean };

export type CallSnapshot = {
  status: CallStatus;
  /** Почему звонок закончился у этого участника; null, пока он идёт. */
  end: CallEnd | null;
  title: string | null;
  role: CallRole;
  marks: CallMarks;
  self: string;
  people: CallPerson[];
  chat: ChatMessage[];
  reactions: ShownReaction[];
  /** Приглашение — ссылка на комнату. */
  link: string;
};

export type VideoKind = "camera" | "screen";

export interface CallSession {
  subscribe(listener: () => void): () => void;
  snapshot(): CallSnapshot;
  setMic(on: boolean): void;
  setCamera(on: boolean): void;
  /** Показ экрана; false — браузер не дал или человек передумал. */
  setScreen(on: boolean): Promise<boolean>;
  setHand(raised: boolean): void;
  /** Реакция; false — лимит 10 за 10 секунд исчерпан. */
  react(emoji: Reaction): boolean;
  sendChat(text: string): Promise<void>;
  lowerHandOf(identity: string): Promise<void>;
  remove(identity: string): Promise<void>;
  /** Выйти самому; звонок для остальных продолжается. */
  leave(): void;
  /** Завершить встречу для всех (владелец). */
  endForAll(): Promise<void>;
  /** Показать видео человека в элементе; null — снять. */
  attach(identity: string, kind: VideoKind, element: HTMLVideoElement | null): void;
}

/** С чем открывается звонок: вход по ссылке, своё имя и свои устройства из лобби. */
export type CallSetup = {
  token: string;
  identity: string;
  name: string;
  role: CallRole;
  title: string | null;
  marks: CallMarks;
  link: string;
  livekit: { url: string; token: string };
  /** Пропуск комнаты для её маршрутов (чат) и id комнаты — у владельца сразу, у остальных из метаданных. */
  roomPass: string;
  roomId: string | null;
  media: { mic: boolean; camera: boolean; stream: MediaStream | null };
};

/** Снимок только что открытого звонка: людей ещё нет, отметки — из входа. */
export const initialSnapshot = (setup: CallSetup): CallSnapshot => ({
  status: "connecting",
  end: null,
  title: setup.title,
  role: setup.role,
  marks: setup.marks,
  self: setup.identity,
  people: [],
  chat: [],
  reactions: [],
  link: setup.link,
});
