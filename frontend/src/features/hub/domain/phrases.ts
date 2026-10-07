import type { Evidence, Gap, ThreadDetail, ThreadStage, ThreadSummary } from "./contract";
import { showCircles } from "./urgency";

/*
 * What the sentences of the Hub are made of, worked out from what the server sent. Only codes, numbers
 * and dates leave here; the UI words them in the interface language (the `hub*` catalogs).
 */

/**
 * The second line of a row: the stage, then what is missing in one phrase. A topic going in circles
 * without a gap says so (`circles`); a promise without a date is never worded as overdue (the server
 * sends `undated`, and only that phrase is used).
 */
export interface RowStatus {
  stage: ThreadStage;
  gap: Gap | null;
  /** "discussed 3 times, no decision", when nothing else is missing. */
  circles: number | null;
}

export function rowStatus(thread: ThreadSummary): RowStatus {
  const circling =
    !thread.gap && showCircles(thread.circles) && thread.stage !== "decided" && thread.stage !== "in_progress";
  return { stage: thread.stage, gap: thread.gap, circles: circling ? thread.circles : null };
}

/** "you dismissed this before", only when a dismissal ran out and the gap came back. */
export const dismissedBefore = (thread: Pick<ThreadSummary, "refutation" | "gap">) =>
  thread.gap !== null && thread.refutation?.returned === true;

/** How often a hub meets, as a named rhythm when there is one: "once a week" rather than "every 7 days". */
export type Rhythm = { kind: "daily" | "weekly" | "biweekly" | "monthly" | "days"; days: number };

export function rhythmOf(days: number): Rhythm {
  if (days <= 1) return { kind: "daily", days };
  if (days === 7) return { kind: "weekly", days };
  if (days === 14) return { kind: "biweekly", days };
  if (days >= 28 && days <= 31) return { kind: "monthly", days };
  return { kind: "days", days };
}

/** A moment in a recording, "32:14" or "1:02:05". */
export function momentLabel(startMs: number): string {
  const total = Math.max(0, Math.floor(startMs / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
}

/** The rounds of the history: the transitions that happened at a meeting. */
export const rounds = (detail: Pick<ThreadDetail, "transitions">) =>
  detail.transitions.filter((t) => t.sessionId !== null);

/** What stood in the way, round by round, as said. */
export const blockers = (detail: Pick<ThreadDetail, "transitions">) =>
  rounds(detail).flatMap((t) => (t.blocker ? [t.blocker.quote] : []));

/** "Discussed 3 times — no decision. Each time it was: …": the rounds, the decision's date, the blockers. */
export interface HistorySummary {
  rounds: number;
  /** When it was decided; null while there is no decision. */
  decidedAt: string | null;
  /** What stood in the way each time; only while there is no decision. */
  blockers: string[];
}

export function historySummary(detail: Pick<ThreadDetail, "transitions" | "decision">): HistorySummary | null {
  const count = rounds(detail).length;
  if (count === 0) return null;
  const decidedAt = detail.decision?.decidedAt ?? null;
  return { rounds: count, decidedAt, blockers: decidedAt ? [] : blockers(detail) };
}

/** The meetings behind a round badge, "came back at three meetings in a row: …": their dates, or null. */
export function circlesHint(detail: Pick<ThreadDetail, "transitions" | "circles">): string[] | null {
  const dates = rounds(detail)
    .filter((t) => t.blocker !== null)
    .slice(-detail.circles)
    .map((t) => t.at);
  return dates.length >= 2 ? dates : null;
}

/**
 * The quote that explains a row's "Why?": the decision behind a contradiction or an orphan decision,
 * otherwise where it started (the promise or the question), and the latest mention for silence.
 */
export function whyEvidence(detail: Pick<ThreadDetail, "gap" | "decision" | "sources">): Evidence | null {
  const kind = detail.gap?.kind;
  if ((kind === "contradiction" || kind === "orphan_decision") && detail.decision) return detail.decision.evidence;
  if (kind === "silence") return detail.sources.at(-1) ?? null;
  return detail.sources[0] ?? detail.decision?.evidence ?? null;
}
