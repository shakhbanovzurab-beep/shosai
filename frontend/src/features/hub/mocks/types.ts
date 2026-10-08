import type { AddressSignal, FactKind, HubKind, Material } from "../domain/contract";
import type { GapKind, ThreadLinkKind, ThreadStage } from "../domain/contract-threads";

/*
 * How the in-memory demo keeps the Hub. Quotes aren't copied: a `Said` points at a line of a
 * recording in Notes (by note id and second), and the evidence is read from there.
 */

export type Said = { note: string; at: number };

/** A gap as the rules found it; its days are counted from `since` (up to it for `due_soon`). */
export type StoredGap = { kind: GapKind; since: string };

export type StoredDismissal = {
  gapKind: GapKind;
  at: string;
  until: string;
  by: "human" | "evidence";
  evidence: string;
};

export type StoredTransition = {
  from: ThreadStage | null;
  to: ThreadStage;
  /** The meeting it happened at; null for a change made by hand (then `at` is set). */
  said: Said | null;
  at?: string;
  by: "machine" | "human";
  blocker: Said | null;
};

export type StoredDecision = { text: string; said: Said };

export type StoredThread = {
  id: string;
  hubId: string;
  subject: string;
  stage: ThreadStage;
  circles: number;
  owner: string | null;
  dueAt: string | null;
  gap: StoredGap | null;
  dismissal: StoredDismissal | null;
  sources: Said[];
  transitions: StoredTransition[];
  decision: StoredDecision | null;
  previousDecision: StoredDecision | null;
  outcome: { text: string; at: string } | null;
  links: { kind: ThreadLinkKind; threadId: string }[];
  /** The meeting it was closed at, for "Closed" in that meeting's digest. */
  closedIn: string | null;
  /** What undo puts back. */
  undo: { stage: ThreadStage; dismissal: StoredDismissal | null } | null;
};

export type StoredFact = {
  id: string;
  kind: FactKind;
  text: string;
  said: Said;
  /** The fact that replaced this decision. */
  supersededBy: string | null;
};

export type StoredHub = {
  id: string;
  name: string;
  kind: HubKind;
  boardId: string | null;
  purpose: string | null;
  success: string | null;
  archived: boolean;
  createdAt: string;
};

export type Filing = { hubId: string; signal: AddressSignal };

/** An upcoming meeting from the calendar whose hub is known. */
export type UpcomingEvent = { id: string; title: string; startsAt: string; hubId: string };

export type HubDemo = {
  hubs: Map<string, StoredHub>;
  threads: Map<string, StoredThread>;
  facts: Map<string, StoredFact[]>;
  materials: Map<string, Material[]>;
  /** Which hub each meeting (note id) is filed in, and why. */
  filings: Map<string, Filing>;
  /** Meetings the server isn't sure about: a suggestion, never a filing. */
  suggestions: Map<string, Filing>;
  /** A person's correction, remembered for the whole calendar series (keyed by series). */
  series: Map<string, string>;
  events: UpcomingEvent[];
  /** When each hub's assistant signal was last delivered. */
  signals: Map<string, string>;
};
