import type { Hub } from "../domain/contract";
import type { Gap, Refutation, ThreadSummary } from "../domain/contract-threads";
import { isOpenStage, mostUrgentGap } from "../domain/urgency";
import { daysBetween } from "./clock";
import { saidAt, sessionStart } from "./sessions";
import { boardName, factsOf, sessionsOf, threadsOf } from "./store";
import type { StoredHub, StoredThread } from "./types";

/*
 * The deterministic rules of the demo server: what is missing and for how many days, counted from
 * the injected now. A dismissal keeps its gap off until it runs out; then the gap comes back and
 * says it was dismissed before.
 */

const dismissalHolds = (thread: StoredThread, now: Date) =>
  thread.dismissal !== null && thread.gap !== null && thread.dismissal.gapKind === thread.gap.kind
    ? Date.parse(thread.dismissal.until) > now.getTime()
    : false;

export function gapOf(thread: StoredThread, now: Date): Gap | null {
  if (!thread.gap || !isOpenStage(thread.stage) || dismissalHolds(thread, now)) return null;
  const { kind, since } = thread.gap;
  return { kind, days: kind === "due_soon" ? daysBetween(now, since) : daysBetween(since, now) };
}

function refutationOf(thread: StoredThread, now: Date): Refutation | null {
  const dismissal = thread.dismissal;
  if (!dismissal) return null;
  return {
    by: dismissal.by,
    at: dismissal.at,
    evidence: dismissal.evidence,
    until: dismissal.until,
    returned: Date.parse(dismissal.until) <= now.getTime(),
  };
}

const latest = (dates: (string | null)[]) =>
  dates.reduce<string | null>((max, date) => (date && (!max || date > max) ? date : max), null);

export function summaryOf(thread: StoredThread, now: Date): ThreadSummary {
  return {
    id: thread.id,
    hubId: thread.hubId,
    subject: thread.subject,
    stage: thread.stage,
    circles: thread.circles,
    gap: gapOf(thread, now),
    owner: thread.owner,
    dueAt: thread.dueAt,
    refutation: refutationOf(thread, now),
    lastDiscussedAt: latest(thread.sources.map(saidAt)),
  };
}

export const openThreadsOf = (hubId: string) => threadsOf(hubId).filter((t) => isOpenStage(t.stage));

/** Median days between meetings, once there are at least three. */
function rhythmOf(sessions: string[]) {
  if (sessions.length < 3) return null;
  const starts = sessions.map((id) => sessionStart(id) ?? "");
  const gaps = starts.slice(1).map((start, i) => daysBetween(starts[i], start));
  const sorted = gaps.sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return Math.round(sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2);
}

export function hubOf(stored: StoredHub, now: Date): Hub {
  const open = openThreadsOf(stored.id);
  const sessions = sessionsOf(stored.id);
  return {
    ...stored,
    boardName: boardName(stored.boardId),
    openThreads: open.length,
    topGap: mostUrgentGap(open.map((t) => gapOf(t, now))),
    rhythmDays: rhythmOf(sessions),
    lastConversationAt: sessions.length > 0 ? sessionStart(sessions[sessions.length - 1]) : null,
    meetingCount: sessions.length,
    agreementCount: factsOf(stored.id).filter((f) => f.kind === "decision" || f.kind === "promise").length,
  };
}
