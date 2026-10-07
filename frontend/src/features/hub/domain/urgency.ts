import type { Gap, GapKind, ThreadStage, ThreadSummary } from "./contract";

/*
 * Ordering what the server found. The server decides what is wrong; the client only sorts it and
 * picks what to show. A contradiction outranks an overdue promise on purpose: hurrying someone to do
 * what was called off is the worst advice there is.
 */

export const GAP_URGENCY: Record<GapKind, number> = {
  contradiction: 1,
  overdue: 2,
  due_soon: 3,
  forgotten: 4,
  undated: 5,
  orphan_decision: 6,
  unanswered: 7,
  silence: 8,
};

/** "What's unresolved" shows at most this many rows. */
export const UNRESOLVED_LIMIT = 12;

/** The round badge appears from the second meeting a topic came back to. */
export const showCircles = (circles: number) => circles >= 2;

/** The colour family of a gap: an independent scale, never the brand accent. */
export type UrgencyTier = "critical" | "soon" | "stale" | "quiet";

export const urgencyTier = (kind: GapKind): UrgencyTier => {
  if (kind === "contradiction" || kind === "overdue") return "critical";
  if (kind === "due_soon") return "soon";
  if (kind === "silence") return "quiet";
  return "stale";
};

const rank = (gap: Gap | null) => (gap ? GAP_URGENCY[gap.kind] : Number.POSITIVE_INFINITY);

const time = (iso: string | null) => (iso ? Date.parse(iso) : 0);

/**
 * Most urgent first: by gap kind, then the longer-standing gap of the same kind, then topics going in
 * circles, then the most recently discussed. Doesn't change the input.
 */
export function byUrgency<T extends Pick<ThreadSummary, "gap" | "circles" | "lastDiscussedAt">>(threads: readonly T[]) {
  return [...threads].sort(
    (a, b) =>
      rank(a.gap) - rank(b.gap) ||
      (b.gap?.days ?? 0) - (a.gap?.days ?? 0) ||
      b.circles - a.circles ||
      time(b.lastDiscussedAt) - time(a.lastDiscussedAt),
  );
}

/** The rows "What's unresolved" shows: the most urgent, up to the limit. */
export const unresolvedRows = <T extends ThreadSummary>(threads: readonly T[]) =>
  byUrgency(threads).slice(0, UNRESOLVED_LIMIT);

/** The most urgent gap among topics, or null when none has one. */
export function mostUrgentGap(gaps: readonly (Gap | null)[]): Gap | null {
  let top: Gap | null = null;
  for (const gap of gaps)
    if (gap && (top === null || rank(gap) < rank(top) || (rank(gap) === rank(top) && gap.days > top.days))) top = gap;
  return top;
}

export const OPEN_STAGES: readonly ThreadStage[] = ["raised", "discussed", "decided", "in_progress"];

export const isOpenStage = (stage: ThreadStage) => OPEN_STAGES.includes(stage);

/** The stage track: the normal path, ending in closed or abandoned. */
export const STAGE_PATH: readonly ThreadStage[] = ["raised", "discussed", "decided", "in_progress", "closed"];
