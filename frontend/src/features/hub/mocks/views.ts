import type { DailyBrief, Digest, FeedPage, MeetingHub, MeetingPrep } from "../domain/contract";
import type { Evidence, ThreadDetail, ThreadTransition } from "../domain/contract-threads";
import { byUrgency, urgencyTier } from "../domain/urgency";
import { openThreadsOf, summaryOf } from "./rules";
import { evidenceOf, seriesOf, sessionOf, sessionStart } from "./sessions";
import { demo, factsOf, findHub, findThread, materialsOf, sessionsOf, threadsOf } from "./store";
import type { StoredDecision, StoredThread, UpcomingEvent } from "./types";

/* What the routes answer with, projected from the stored demo. */

const present = <T>(value: T | null): value is T => value !== null;

const decisionOf = (decision: StoredDecision | null) => {
  const evidence = decision ? evidenceOf(decision.said) : null;
  return decision && evidence ? { text: decision.text, decidedAt: evidence.meetingStartedAt, evidence } : null;
};

function transitionOf(t: StoredThread["transitions"][number]): ThreadTransition {
  const session = t.said ? sessionOf(t.said.note) : null;
  return {
    from: t.from,
    to: t.to,
    at: session?.startedAt ?? t.at ?? new Date().toISOString(),
    sessionId: session?.id ?? null,
    meetingTitle: session?.title ?? null,
    by: t.by,
    blocker: t.blocker ? evidenceOf(t.blocker) : null,
  };
}

export function detailOf(thread: StoredThread, now: Date): ThreadDetail {
  return {
    ...summaryOf(thread, now),
    transitions: thread.transitions.map(transitionOf),
    sources: thread.sources.map(evidenceOf).filter(present),
    decision: decisionOf(thread.decision),
    previousDecision: decisionOf(thread.previousDecision),
    outcome: thread.outcome,
    links: thread.links.flatMap(({ kind, threadId }) => {
      const linked = findThread(threadId);
      return linked ? [{ kind, thread: summaryOf(linked, now) }] : [];
    }),
  };
}

const mentionedIn = (thread: StoredThread, sessionId: string) => thread.sources.some((s) => s.note === sessionId);

/** Appeared, closed, and — the main block — holds the hub up yet wasn't mentioned. */
export function digestOf(hubId: string, sessionId: string, now: Date): Digest | null {
  const sessions = sessionsOf(hubId);
  const id = sessionId === "latest" ? sessions.at(-1) : sessions.find((s) => s === sessionId);
  const session = id ? sessionOf(id) : null;
  if (!id || !session) return null;
  const threads = threadsOf(hubId);
  return {
    sessionId: id,
    meetingTitle: session.title,
    meetingStartedAt: session.startedAt,
    opened: threads.filter((t) => t.sources[0]?.note === id && t.closedIn !== id).map((t) => summaryOf(t, now)),
    closed: threads.filter((t) => t.closedIn === id).map((t) => summaryOf(t, now)),
    untouched: openThreadsOf(hubId)
      .filter((t) => t.circles >= 2 && !mentionedIn(t, id))
      .map((t) => summaryOf(t, now)),
  };
}

export const FEED_PAGE = 20;

export function feedOf(hubId: string, cursor: string | null): FeedPage {
  const facts = factsOf(hubId);
  const sessions = sessionsOf(hubId).reverse();
  const start = Math.max(0, Number(cursor) || 0);
  const page = sessions.slice(start, start + FEED_PAGE);
  return {
    meetings: page.flatMap((id) => {
      const session = sessionOf(id);
      if (!session) return [];
      const own = facts.filter((f) => f.said.note === id);
      return [
        {
          sessionId: id,
          meetingTitle: session.title,
          meetingStartedAt: session.startedAt,
          facts: own.map((f) => {
            const evidence: Evidence | null = evidenceOf(f.said);
            const by = f.supersededBy ? facts.find((other) => other.id === f.supersededBy) : undefined;
            const bySession = by ? sessionOf(by.said.note) : null;
            return {
              id: f.id,
              kind: f.kind,
              text: f.text,
              speaker: evidence?.speaker ?? null,
              startMs: evidence?.startMs ?? null,
              supersededBy:
                by && bySession
                  ? { text: by.text, sessionId: bySession.id, meetingTitle: bySession.title, at: bySession.startedAt }
                  : null,
            };
          }),
        },
      ];
    }),
    nextCursor: start + FEED_PAGE < sessions.length ? String(start + FEED_PAGE) : null,
  };
}

/** Only what is really on fire: contradictions, overdue and due soon; up to 3 per hub, about 7 in all. */
export function briefOf(now: Date): DailyBrief {
  const items = [...demo.hubs.values()]
    .filter((h) => !h.archived)
    .flatMap((h) =>
      byUrgency(openThreadsOf(h.id).map((t) => summaryOf(t, now)))
        .filter((t) => t.gap !== null && ["critical", "soon"].includes(urgencyTier(t.gap.kind)))
        .slice(0, 3)
        .map((thread) => ({ hub: { id: h.id, name: h.name }, thread })),
    )
    .slice(0, 7);
  return { date: now.toISOString().slice(0, 10), items };
}

export function prepOf(event: UpcomingEvent, now: Date): MeetingPrep | null {
  const hub = findHub(event.hubId);
  if (!hub || hub.archived) return null;
  const open = byUrgency(openThreadsOf(hub.id).map((t) => summaryOf(t, now))).slice(0, 5);
  const lastDigest = digestOf(hub.id, "latest", now);
  const materials = materialsOf(hub.id)
    .filter((m) => !m.gone)
    .slice(0, 3);
  // Nothing to say: no card at all.
  if (open.length === 0 && !lastDigest && materials.length === 0) return null;
  return {
    sessionOrEventId: event.id,
    meetingTitle: event.title,
    hub: { id: hub.id, name: hub.name },
    startsAt: event.startsAt,
    open,
    lastDigest,
    materials,
  };
}

/** Upcoming meetings with a known hub in the next week, soonest first. */
export const upcomingPreps = (now: Date) =>
  demo.events
    .filter((e) => Date.parse(e.startsAt) > now.getTime() && Date.parse(e.startsAt) - now.getTime() < 7 * 86_400_000)
    .sort((a, b) => a.startsAt.localeCompare(b.startsAt))
    .map((e) => prepOf(e, now))
    .filter(present);

/** The hub a meeting is in; else the series a person filed before; else a suggestion; else nothing. */
export function meetingHubOf(sessionId: string): MeetingHub {
  const filing = demo.filings.get(sessionId);
  const rememberedId = demo.series.get(seriesOf(sessionId));
  const hub = findHub(filing?.hubId ?? rememberedId ?? "");
  if (hub)
    return {
      hub: { id: hub.id, name: hub.name, boardId: hub.boardId, archived: hub.archived },
      signal: filing?.signal ?? "series",
      suggestion: null,
    };
  const suggested = demo.suggestions.get(sessionId);
  const target = suggested ? findHub(suggested.hubId) : null;
  if (suggested && target && !target.archived)
    return {
      hub: null,
      signal: null,
      suggestion: { hub: { id: target.id, name: target.name }, signal: suggested.signal },
    };
  return { hub: null, signal: null, suggestion: null };
}

export const sessionKnown = (sessionId: string) => sessionStart(sessionId) !== null;
