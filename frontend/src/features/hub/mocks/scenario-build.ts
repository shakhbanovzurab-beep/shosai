import type { FactKind, Material } from "../domain/contract";
import type { ThreadStage } from "../domain/contract-threads";
import type { Said, StoredDecision, StoredFact, StoredThread, StoredTransition, UpcomingEvent } from "./types";

/*
 * Small builders that keep the demo scenario readable. Subjects, decisions, facts, material and meeting
 * titles are what people said or wrote, so they stay as written in every interface language.
 */

export const said = (note: string, at: number): Said => ({ note, at });

export const step = (
  from: ThreadStage | null,
  to: ThreadStage,
  at: Said,
  blocker: Said | null = null,
): StoredTransition => ({ from, to, said: at, by: "machine", blocker });

/** A round of a topic going in circles: it came back, didn't move, and this stood in the way. */
export const round = (at: Said, blocker: Said): StoredTransition => step("discussed", "discussed", at, blocker);

export function thread(
  id: string,
  hubId: string,
  subject: string,
  fields: Partial<Omit<StoredThread, "id" | "hubId" | "subject">> & Pick<StoredThread, "stage" | "sources">,
): StoredThread {
  return {
    id,
    hubId,
    subject,
    circles: 0,
    owner: null,
    dueAt: null,
    gap: null,
    dismissal: null,
    transitions: [],
    decision: null,
    previousDecision: null,
    outcome: null,
    links: [],
    closedIn: null,
    undo: null,
    ...fields,
  };
}

export const fact = (
  id: string,
  kind: FactKind,
  text: string,
  at: Said,
  supersededBy: string | null = null,
): StoredFact => ({ id, kind, text, said: at, supersededBy });

export const decided = (text: string, at: Said): StoredDecision => ({ text, said: at });

/** A material of a hub: a meeting's summary (with its note id) or a file added by hand (`sessionId` null). */
export const material = (
  id: string,
  kind: Material["kind"],
  title: string,
  where: { sessionId: string | null; url: string | null; addedAt: string; gone?: boolean },
): Material => ({
  id,
  kind,
  title,
  sessionId: where.sessionId,
  url: where.url,
  addedAt: where.addedAt,
  gone: where.gone ?? false,
});

export const upcoming = (id: string, title: string, startsAt: string, hubId: string): UpcomingEvent => ({
  id,
  title,
  startsAt,
  hubId,
});
