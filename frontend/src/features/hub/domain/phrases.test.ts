import { describe, it } from "vitest";

import type { Evidence, GapKind, ThreadDetail, ThreadSummary, ThreadTransition } from "./contract-threads";
import { circlesHint, dismissedBefore, historySummary, momentLabel, rhythmOf, rowStatus, whyEvidence } from "./phrases";
import assert from "node:assert/strict";

const summary = (extra: Partial<ThreadSummary> = {}): ThreadSummary => ({
  id: "t",
  hubId: "h",
  subject: "Договор поставки",
  stage: "discussed",
  circles: 0,
  gap: null,
  owner: null,
  dueAt: null,
  refutation: null,
  lastDiscussedAt: null,
  ...extra,
});

const said = (quote: string, at = "2026-09-12T10:00:00Z"): Evidence => ({
  sessionId: `s-${quote}`,
  meetingTitle: "Синк",
  meetingStartedAt: at,
  speaker: null,
  startMs: null,
  quote,
});

const round = (at: string, blocker: string | null): ThreadTransition => ({
  from: "discussed",
  to: "discussed",
  at,
  sessionId: `s-${at}`,
  meetingTitle: "Синк",
  by: "machine",
  blocker: blocker ? said(blocker, at) : null,
});

describe("rowStatus", () => {
  it("is the stage and the gap", () => {
    const gap = { kind: "overdue" as const, days: 1 };
    assert.deepEqual(rowStatus(summary({ gap })), { stage: "discussed", gap, circles: null });
  });

  it("keeps a promise without a date as undated, never overdue", () => {
    assert.equal(rowStatus(summary({ gap: { kind: "undated", days: 40 } })).gap?.kind, "undated");
  });

  it("says a topic went in circles when nothing else is missing", () => {
    assert.equal(rowStatus(summary({ circles: 3 })).circles, 3);
    assert.equal(rowStatus(summary({ circles: 3, gap: { kind: "silence", days: 2 } })).circles, null);
    assert.equal(rowStatus(summary({ circles: 3, stage: "decided" })).circles, null);
  });

  it("is just the stage otherwise", () => {
    assert.deepEqual(rowStatus(summary({ circles: 1 })), { stage: "discussed", gap: null, circles: null });
  });
});

describe("dismissedBefore", () => {
  const refutation = { by: "human" as const, at: "2026-07-06", evidence: "", until: "2026-10-04", returned: true };
  it("explains a gap that came back after a dismissal", () => {
    assert.equal(dismissedBefore({ gap: { kind: "forgotten", days: 15 }, refutation }), true);
  });
  it("stays quiet while the dismissal holds", () => {
    assert.equal(dismissedBefore({ gap: null, refutation: { ...refutation, returned: false } }), false);
  });
});

describe("rhythmOf", () => {
  it("names the usual rhythms and counts the rest in days", () => {
    assert.equal(rhythmOf(1).kind, "daily");
    assert.equal(rhythmOf(7).kind, "weekly");
    assert.equal(rhythmOf(14).kind, "biweekly");
    assert.equal(rhythmOf(30).kind, "monthly");
    assert.deepEqual(rhythmOf(10), { kind: "days", days: 10 });
  });
});

describe("momentLabel", () => {
  it("formats a moment in the recording", () => {
    assert.equal(momentLabel(1_934_000), "32:14");
    assert.equal(momentLabel(5_000), "0:05");
    assert.equal(momentLabel(3_725_000), "1:02:05");
  });
});

const contract = {
  transitions: [
    round("2026-09-12T10:00:00Z", "ждём юристов клиента"),
    round("2026-09-19T10:00:00Z", "не согласована цена за место"),
    round("2026-09-26T10:00:00Z", "перенесли на следующую неделю"),
  ],
  decision: null,
  circles: 3,
};

describe("historySummary", () => {
  it("sums up the rounds and what stood in the way each time", () => {
    assert.deepEqual(historySummary(contract), {
      rounds: 3,
      decidedAt: null,
      blockers: ["ждём юристов клиента", "не согласована цена за место", "перенесли на следующую неделю"],
    });
  });

  it("names the date once there is a decision", () => {
    const decided = { ...contract, decision: { text: "Да", decidedAt: "2026-09-24T10:00:00Z", evidence: said("Да") } };
    assert.deepEqual(historySummary(decided), { rounds: 3, decidedAt: "2026-09-24T10:00:00Z", blockers: [] });
  });

  it("is null without rounds", () => {
    assert.equal(historySummary({ transitions: [], decision: null }), null);
  });
});

describe("circlesHint", () => {
  it("lists the meetings the topic came back to", () => {
    assert.deepEqual(circlesHint(contract), ["2026-09-12T10:00:00Z", "2026-09-19T10:00:00Z", "2026-09-26T10:00:00Z"]);
  });
  it("is null for fewer than two meetings", () => {
    assert.equal(circlesHint({ ...contract, circles: 1 }), null);
  });
});

describe("whyEvidence", () => {
  const decision = { text: "Добавляем", decidedAt: "2026-09-24T10:00:00Z", evidence: said("Давайте добавим Telegram") };
  const sources = [said("Сделаю макет"), said("Последнее упоминание")];
  const detail = (kind: GapKind | null): Pick<ThreadDetail, "gap" | "decision" | "sources"> => ({
    gap: kind ? { kind, days: 1 } : null,
    decision,
    sources,
  });
  it("points a contradiction at the decision", () => {
    assert.equal(whyEvidence(detail("contradiction"))?.quote, "Давайте добавим Telegram");
  });
  it("points a promise at where it was made", () => {
    assert.equal(whyEvidence(detail("overdue"))?.quote, "Сделаю макет");
  });
  it("points silence at the last mention", () => {
    assert.equal(whyEvidence(detail("silence"))?.quote, "Последнее упоминание");
  });
});
