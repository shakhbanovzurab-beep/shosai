import { describe, it } from "vitest";

import type { MeetingCard } from "../domain/library";
import { merged } from "./library-resource";
import assert from "node:assert/strict";

const card = (id: string, day: number): MeetingCard => ({
  id,
  title: id,
  status: "completed",
  startedAt: `2026-10-${String(day).padStart(2, "0")}T09:00:00Z`,
  durationMinutes: 30,
  owned: true,
  participantNames: [],
  participantCount: 1,
  summary: null,
  keyPoints: [],
  firstDecision: null,
  actionItems: 0,
  notes: "ready",
});

const ids = (items: readonly MeetingCard[]) => items.map((item) => item.id);

describe("merged", () => {
  it("takes the first page as it is when nothing more was read", () => {
    const pages = merged(null, [card("b", 20), card("a", 19)], "c1");

    assert.deepEqual(ids(pages.items), ["b", "a"]);
    assert.equal(pages.nextCursor, "c1");
  });

  it("keeps the pages read further, and their cursor, under a fresh first page", () => {
    const previous = { items: [card("c", 20), card("b", 19), card("a", 18)], nextCursor: "c2" };

    const pages = merged(previous, [card("d", 21), card("c", 20)], "c1");

    assert.deepEqual(ids(pages.items), ["d", "c", "b", "a"]);
    assert.equal(pages.nextCursor, "c2");
  });

  it("drops a meeting from the tail once the fresh page holds it", () => {
    const previous = { items: [card("c", 20), card("b", 19), card("a", 18)], nextCursor: "c2" };

    const pages = merged(previous, [card("b", 19), card("c", 20)], "c1");

    assert.deepEqual(ids(pages.items), ["b", "c", "a"]);
  });

  it("puts new meetings on top of the pages already read", () => {
    const previous = { items: [card("c", 20), card("b", 19), card("a", 18)], nextCursor: "c2" };

    const pages = merged(previous, [card("e", 22), card("d", 21)], "c1");

    assert.deepEqual(ids(pages.items), ["e", "d", "c", "b", "a"]);
    assert.equal(pages.nextCursor, "c2");
  });

  it("follows the fresh page and its cursor when nothing is left past it", () => {
    const previous = { items: [card("c", 20), card("b", 19), card("a", 18)], nextCursor: "c2" };

    const pages = merged(previous, [card("c", 20), card("a", 18)], "c1");

    assert.deepEqual(ids(pages.items), ["c", "a"]);
    assert.equal(pages.nextCursor, "c1");
  });
});
