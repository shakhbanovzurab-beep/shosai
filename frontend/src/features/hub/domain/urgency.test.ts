import { describe, it } from "vitest";

import type { Gap, GapKind, ThreadSummary } from "./contract-threads";
import { byUrgency, mostUrgentGap, showCircles, UNRESOLVED_LIMIT, unresolvedRows, urgencyTier } from "./urgency";
import assert from "node:assert/strict";

const row = (id: string, gap: Gap | null, extra: Partial<ThreadSummary> = {}): ThreadSummary => ({
  id,
  hubId: "h",
  subject: id,
  stage: "discussed",
  circles: 0,
  gap,
  owner: null,
  dueAt: null,
  refutation: null,
  lastDiscussedAt: null,
  ...extra,
});

const ORDER: GapKind[] = [
  "contradiction",
  "overdue",
  "due_soon",
  "forgotten",
  "undated",
  "orphan_decision",
  "unanswered",
  "silence",
];

describe("byUrgency", () => {
  it("follows the urgency of the specification, contradiction before overdue", () => {
    const shuffled = [...ORDER].reverse().map((kind) => row(kind, { kind, days: 1 }));
    assert.deepEqual(
      byUrgency(shuffled).map((t) => t.id),
      ORDER,
    );
  });

  it("puts rows without a gap last, those going in circles first among them", () => {
    const sorted = byUrgency([
      row("quiet", null),
      row("circling", null, { circles: 3 }),
      row("silence", { kind: "silence", days: 23 }),
    ]);
    assert.deepEqual(
      sorted.map((t) => t.id),
      ["silence", "circling", "quiet"],
    );
  });

  it("puts the longer-standing gap of the same kind first", () => {
    const sorted = byUrgency([row("a", { kind: "overdue", days: 1 }), row("b", { kind: "overdue", days: 6 })]);
    assert.deepEqual(
      sorted.map((t) => t.id),
      ["b", "a"],
    );
  });

  it("then the most recently discussed", () => {
    const sorted = byUrgency([
      row("older", null, { lastDiscussedAt: "2026-09-01T10:00:00Z" }),
      row("newer", null, { lastDiscussedAt: "2026-10-01T10:00:00Z" }),
    ]);
    assert.equal(sorted[0].id, "newer");
  });

  it("leaves its input as it was", () => {
    const input = [row("b", null), row("a", { kind: "overdue", days: 1 })];
    byUrgency(input);
    assert.equal(input[0].id, "b");
  });
});

describe("unresolvedRows", () => {
  it("shows at most twelve rows, the most urgent ones", () => {
    const many = Array.from({ length: 20 }, (_, i) => row(`t${i}`, i === 19 ? { kind: "overdue", days: 2 } : null));
    const rows = unresolvedRows(many);
    assert.equal(UNRESOLVED_LIMIT, 12);
    assert.equal(rows.length, 12);
    assert.equal(rows[0].id, "t19");
  });
});

describe("mostUrgentGap", () => {
  it("picks the most urgent kind, then the oldest", () => {
    assert.deepEqual(
      mostUrgentGap([{ kind: "undated", days: 17 }, null, { kind: "overdue", days: 1 }, { kind: "overdue", days: 4 }]),
      { kind: "overdue", days: 4 },
    );
  });

  it("is null when nothing is missing", () => {
    assert.equal(mostUrgentGap([null, null]), null);
  });
});

describe("showCircles", () => {
  it("shows the round badge from the second round", () => {
    assert.equal(showCircles(0), false);
    assert.equal(showCircles(1), false);
    assert.equal(showCircles(2), true);
    assert.equal(showCircles(3), true);
  });
});

describe("urgencyTier", () => {
  it("keeps four tiers: contradictions and overdue, due soon, forgotten and undated, silence", () => {
    assert.equal(urgencyTier("contradiction"), "critical");
    assert.equal(urgencyTier("overdue"), "critical");
    assert.equal(urgencyTier("due_soon"), "soon");
    assert.equal(urgencyTier("forgotten"), "stale");
    assert.equal(urgencyTier("undated"), "stale");
    assert.equal(urgencyTier("silence"), "quiet");
  });
});
