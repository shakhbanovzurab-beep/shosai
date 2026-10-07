/* The Hub's topics: what is missing, where it was said, and how each one got where it is. Part of ./contract.ts. */

export type ThreadStage = "raised" | "discussed" | "decided" | "in_progress" | "closed" | "abandoned";

export type GapKind =
  | "contradiction"
  | "overdue"
  | "due_soon"
  | "forgotten"
  | "undated"
  | "orphan_decision"
  | "unanswered"
  | "silence";

/** What is missing right now. The server finds it; the client only words and sorts it. */
export interface Gap {
  kind: GapKind;
  days: number;
}

export interface Evidence {
  sessionId: string;
  meetingTitle: string;
  meetingStartedAt: string;
  /** Null: nobody is named, so no "Said by" line. */
  speaker: string | null;
  /** Null: no link to the moment. */
  startMs: number | null;
  quote: string;
}

export interface Refutation {
  by: "human" | "evidence";
  /** When it was dismissed. */
  at: string;
  /** What disproved it, for `evidence` ("an email with the attachment on 09.09"); empty for a person. */
  evidence: string;
  until: string | null;
  /** The dismissal ran out and the gap came back. */
  returned: boolean;
}

/** One row of "What's unresolved"; a hub's rows come in one request. */
export interface ThreadSummary {
  id: string;
  hubId: string;
  subject: string;
  stage: ThreadStage;
  /** Meetings it came back to without moving; counted by the server. */
  circles: number;
  gap: Gap | null;
  /** Null is a valid state: the row offers "Assign". */
  owner: string | null;
  dueAt: string | null;
  refutation: Refutation | null;
  lastDiscussedAt: string | null;
}

export interface ThreadTransition {
  from: ThreadStage | null;
  to: ThreadStage;
  at: string;
  sessionId: string | null;
  meetingTitle: string | null;
  by: "machine" | "human";
  /** What stood in the way at this round, as said. */
  blocker: Evidence | null;
}

export type ThreadLinkKind = "causes" | "blocked_by" | "outcome_of";

export interface ThreadDecision {
  text: string;
  decidedAt: string;
  evidence: Evidence;
}

export interface ThreadDetail extends ThreadSummary {
  /** In time order. */
  transitions: ThreadTransition[];
  /** Every mention, in time order. */
  sources: Evidence[];
  decision: ThreadDecision | null;
  /** An earlier decision the current one reversed; set for a contradiction. */
  previousDecision: ThreadDecision | null;
  /** How the decision turned out; null while it isn't known. */
  outcome: { text: string; at: string } | null;
  links: { kind: ThreadLinkKind; thread: ThreadSummary }[];
}
