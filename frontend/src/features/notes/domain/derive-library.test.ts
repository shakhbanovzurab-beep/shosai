import { describe, it } from "vitest";

import { activeFolderOf, deriveLibrary } from "./derive-library";
import type { MeetingCard } from "./library";
import assert from "node:assert/strict";

const folders = [{ id: "f1", name: "Sales", color: "blue" as const }];

const card = (id: string, startedAt: string): MeetingCard => ({
  id,
  title: id,
  status: "completed",
  startedAt,
  durationMinutes: 30,
  owned: true,
  participantNames: [],
  participantCount: 1,
  source: "live",
  summary: null,
  keyPoints: [],
  firstDecision: null,
  actionItems: 0,
  notes: "ready",
});

describe("activeFolderOf", () => {
  it("shows every meeting for an unknown or deleted folder in the address", () => {
    assert.equal(activeFolderOf(folders, "f1"), "f1");
    assert.equal(activeFolderOf(folders, "gone"), undefined);
    assert.equal(activeFolderOf(folders, undefined), undefined);
  });

  it("trusts the address until the folders are read", () => {
    assert.equal(activeFolderOf(null, "f1"), "f1");
  });
});

describe("deriveLibrary", () => {
  const items = [card("new", "2026-10-20T09:00:00Z"), card("old", "2026-10-19T09:00:00Z")];

  it("gives the newest meeting the large card only in the grid of all meetings", () => {
    assert.equal(deriveLibrary(items, undefined, "grid", "UTC").featured?.id, "new");
    assert.equal(deriveLibrary(items, "f1", "grid", "UTC").featured, undefined);
    assert.equal(deriveLibrary(items, undefined, "list", "UTC").featured, undefined);
  });

  it("leaves the large card to an upload that took it, and groups every meeting", () => {
    const { featured, groups } = deriveLibrary(items, undefined, "grid", "UTC", true);

    assert.equal(featured, undefined);
    assert.deepEqual(
      groups.flatMap((group) => group.items.map((note) => note.id)),
      ["new", "old"],
    );
  });

  it("groups the rest by recency without the featured meeting", () => {
    const { groups } = deriveLibrary(items, undefined, "grid", "UTC");
    const ids = groups.flatMap((group) => group.items.map((note) => note.id));

    assert.deepEqual(ids, ["old"]);
  });
});
