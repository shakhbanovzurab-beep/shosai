import type { CallSession } from "./call-session";

/*
 * Трансляция (MR-D7): сцена говорит, зал смотрит. Сцена — ведущий, соведущие и до 10 спикеров — собирается до
 * начала; зал входит только в эфир, до 100 зрителей, через зал ожидания, если его включил ведущий. Зритель ничего
 * не публикует: чат, реакции и поднятая рука идут через маршруты сервера. Домен не знает LiveKit.
 */

export const VIEWERS_MAX = 100;
export const SPEAKERS_MAX = 10;

export type BroadcastStatus = "scheduled" | "live" | "ended";
export type StageRole = "host" | "cohost" | "speaker";

/** Что ответила ссылка: сцена, зал, ожидание впуска, ещё не в эфире, мест нет, закончилась. */
export type BroadcastEntry = "stage" | "audience" | "wait" | "not_live" | "full" | "ended";

/** Ответ ссылки этому человеку: куда он попадает, его роль на сцене и его сессия. */
export type BroadcastTicket = {
  entry: BroadcastEntry;
  title: string;
  role: StageRole | null;
  waitingRoom: boolean;
  identity: string;
  /** Пропуски сессии — когда ссылка впустила: LiveKit и пропуск комнаты для маршрутов трансляции. */
  access: { livekitUrl: string; livekitToken: string; roomPass: string } | null;
  /** С ним зритель снова спрашивает о впуске, пока ждёт. */
  knock: string | null;
  /** Только у ведущего: начать и закончить эфир. */
  broadcastId: string | null;
};

/** Человек на сцене; `onAir: false` — ведущий убрал его из эфира, не снимая со сцены. */
export type StageMember = { principal: string; identity: string | null; name: string; role: StageRole; onAir: boolean };

/** Зритель поднял руку — просит слова; ведущий зовёт его на сцену или отклоняет. */
export type HandRequest = { id: string; principal: string; name: string; at: string };

/** Зритель ждёт впуска в зале ожидания. */
export type Admission = { id: string; name: string; at: string };

export type BroadcastMessage = {
  id: string;
  seq: number;
  author: string;
  text: string;
  sentAt: string;
  /** Сообщение сцены: зал видит его отмеченным. */
  fromStage: boolean;
  mine: boolean;
};

/** Своя рука зрителя: опущена, поднята или ведущий зовёт на сцену. */
export type OwnHand = "down" | "raised" | "invited";

export type BroadcastSnapshot = {
  status: BroadcastStatus;
  title: string;
  /** Своя роль на сцене; null — зритель. */
  role: StageRole | null;
  members: StageMember[];
  /** Зрителей в эфире; null — неизвестно (SFU не ответил), это не ноль. */
  viewers: number | null;
  waitingRoom: boolean;
  hands: HandRequest[];
  admissions: Admission[];
  chat: BroadcastMessage[];
  hand: OwnHand;
  startedAt: string | null;
};

/** Трансляция для экрана: сцена — звонок её участников, остальное — её собственное состояние. */
export interface BroadcastSession {
  /** Видео и свои устройства сцены; у зрителя — только эфирная часть сцены. */
  readonly call: CallSession;
  subscribe(listener: () => void): () => void;
  snapshot(): BroadcastSnapshot;
  start(): Promise<void>;
  end(): Promise<void>;
  sendChat(text: string): Promise<void>;
  raiseHand(raised: boolean): Promise<void>;
  /** Зритель принял приглашение ведущего: выходит на сцену со своими устройствами. */
  acceptInvite(): Promise<void>;
  answerHand(id: string, invite: boolean): Promise<void>;
  admit(id: string, admitted: boolean): Promise<void>;
  setOnAir(principal: string, onAir: boolean): Promise<void>;
  setCohost(principal: string, cohost: boolean): Promise<void>;
  removeFromStage(principal: string): Promise<void>;
  leave(): void;
}

/** Ведущий и соведущие управляют сценой, очередями и чатом. */
export const mayModerate = (role: StageRole | null) => role === "host" || role === "cohost";

/** Соведущих назначает и снимает только ведущий: право нельзя отнять у него самого. */
export const mayManageCohosts = (role: StageRole | null) => role === "host";

/** Спикеров, кроме ведущего, на сцене не больше десяти. */
export function stageIsFull(members: readonly StageMember[]): boolean {
  return members.filter((member) => member.role !== "host").length >= SPEAKERS_MAX;
}

/** Кого видит зал: сцена в эфире, ведущий первым. */
export function onAir(members: readonly StageMember[]): StageMember[] {
  const order: Record<StageRole, number> = { host: 0, cohost: 1, speaker: 2 };
  return members.filter((member) => member.onAir).toSorted((a, b) => order[a.role] - order[b.role]);
}
