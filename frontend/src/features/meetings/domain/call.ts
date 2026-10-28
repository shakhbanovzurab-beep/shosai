/* Звонок комнаты Shosai, каким его видит кабинет: люди по сессиям LiveKit, сцена из видео и руки (MR-D6, MR-D12). */

/** Сколько видео показывает сцена: говорящий, недавние говорящие и закреплённые (meetings §1.3). */
export const MAX_VIDEO_TILES = 6;
/** Разделитель identity LiveKit: `<принципал>__<8 hex>`; identity без него (egress) — не человек. */
const SESSION_SEPARATOR = "__";
const SESSION = /^[0-9a-f]{8}$/;

export type CallRole = "owner" | "participant";

/** Одна сессия звонка: человек или гость на одном устройстве. */
export type CallPerson = {
  identity: string;
  name: string;
  isLocal: boolean;
  isOwner: boolean;
  micOn: boolean;
  cameraOn: boolean;
  screenOn: boolean;
  speaking: boolean;
  /** Когда человек говорил последним (мс), 0 — ещё не говорил. */
  lastSpokeAt: number;
  /** Когда поднята рука (ISO), null — опущена. */
  hand: string | null;
};

/** Принципал сессии: id человека или `guest-…`; null для identity, которую выдал не Shosai. */
export function principalOf(identity: string): string | null {
  const at = identity.lastIndexOf(SESSION_SEPARATOR);
  if (at <= 0) return null;
  return SESSION.test(identity.slice(at + SESSION_SEPARATOR.length)) ? identity.slice(0, at) : null;
}

/** Люди звонка: без технических участников (egress), в порядке входа. */
export const peopleOf = <T extends { identity: string }>(sessions: T[]) =>
  sessions.filter((session) => principalOf(session.identity) !== null);

export type Stage = { tiles: CallPerson[]; others: CallPerson[] };

const spokeLater = (a: CallPerson, b: CallPerson) => b.lastSpokeAt - a.lastSpokeAt;

/**
 * Кому на сцене видео: закреплённые, показывающие экран, говорящие сейчас, затем говорившие недавно и свой кадр.
 * Небольшой звонок помещается целиком; остальные — аватарами.
 */
export function stageOf(people: CallPerson[], pinned: ReadonlySet<string>, max = MAX_VIDEO_TILES): Stage {
  const rank = (person: CallPerson) => {
    if (pinned.has(person.identity)) return 0;
    if (person.screenOn) return 1;
    if (person.speaking) return 2;
    if (person.lastSpokeAt > 0) return 3;
    return person.isLocal ? 4 : 5;
  };
  const ordered = people.toSorted((a, b) => rank(a) - rank(b) || spokeLater(a, b));
  const chosen = new Set(ordered.slice(0, max).map((person) => person.identity));
  // Плитки стоят в порядке входа: сцена не прыгает, когда говорит другой.
  return {
    tiles: people.filter((person) => chosen.has(person.identity)),
    others: people.filter((person) => !chosen.has(person.identity)),
  };
}

/** Поднятые руки по времени: кто раньше поднял, тот выше. */
export const raisedHands = (people: CallPerson[]) =>
  people.filter((person) => person.hand !== null).toSorted((a, b) => (a.hand ?? "").localeCompare(b.hand ?? ""));

/** Убрать человека может только владелец, и не себя. */
export const mayRemove = (role: CallRole, person: CallPerson) => role === "owner" && !person.isOwner && !person.isLocal;

/** Инициалы для аватара: первые буквы двух первых слов имени. */
export const initialsOf = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => [...word][0] ?? "")
    .join("")
    .toUpperCase();
