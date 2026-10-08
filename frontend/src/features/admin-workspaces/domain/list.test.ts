import { describe, it } from "vitest";

import type { AdminWorkspace } from "./contract";
import { plural } from "./format";
import { applyFilter, DEFAULT_FILTER, needsAttention, totals } from "./list";
import assert from "node:assert/strict";

const NOW = Date.parse("2026-10-07T12:00:00Z");
const daysAgo = (days: number) => new Date(NOW - days * 86_400_000).toISOString();

const row = (id: string, extra: Partial<AdminWorkspace> = {}): AdminWorkspace => ({
  id,
  name: id,
  slug: id,
  owner: { name: `${id} owner`, email: `owner@${id}.com` },
  plan: { name: "Team", seats: 10, price_per_seat_cents: 2000, currency: "USD", renews_at: daysAgo(-20) },
  status: "active",
  trial_ends_at: null,
  members: 5,
  pending_invitations: 0,
  seats_used: 5,
  monthly_cents: 20_000,
  meetings_month: 10,
  minutes_month: 300,
  last_active_at: daysAgo(1),
  created_at: daysAgo(100),
  ...extra,
});

describe("needsAttention", () => {
  it("flags suspended, unpaid, full and quiet workspaces", () => {
    assert.equal(needsAttention(row("a"), NOW), false);
    assert.equal(needsAttention(row("b", { status: "suspended" }), NOW), true);
    assert.equal(needsAttention(row("c", { status: "past_due" }), NOW), true);
    assert.equal(needsAttention(row("d", { seats_used: 10 }), NOW), true);
    assert.equal(needsAttention(row("e", { last_active_at: daysAgo(20) }), NOW), true);
    assert.equal(needsAttention(row("f", { last_active_at: null }), NOW), true);
  });
});

describe("applyFilter", () => {
  const rows = [
    row("acme", { minutes_month: 100 }),
    row("bright", { status: "past_due", minutes_month: 50 }),
    row("orbit", { plan: { ...row("x").plan, name: "Enterprise" }, minutes_month: 900 }),
  ];

  it("puts what needs attention first by default", () => {
    assert.deepEqual(
      applyFilter(rows, DEFAULT_FILTER).map((w) => w.id),
      ["bright", "acme", "orbit"],
    );
  });

  it("filters by status, plan and text, including the owner's email", () => {
    assert.deepEqual(
      applyFilter(rows, { ...DEFAULT_FILTER, status: "past_due" }).map((w) => w.id),
      ["bright"],
    );
    assert.deepEqual(
      applyFilter(rows, { ...DEFAULT_FILTER, plan: "Enterprise" }).map((w) => w.id),
      ["orbit"],
    );
    assert.deepEqual(
      applyFilter(rows, { ...DEFAULT_FILTER, q: "OWNER@ACME" }).map((w) => w.id),
      ["acme"],
    );
  });

  it("sorts by activity", () => {
    assert.deepEqual(
      applyFilter(rows, { ...DEFAULT_FILTER, sort: "minutes" }).map((w) => w.id),
      ["orbit", "acme", "bright"],
    );
  });
});

describe("totals", () => {
  it("leaves suspended workspaces out of revenue", () => {
    const sum = totals([row("a"), row("b", { status: "suspended" })]);
    assert.equal(sum.monthly, 20_000);
    assert.equal(sum.seats, 20);
    assert.equal(sum.active, 1);
  });
});

describe("plural", () => {
  it("uses the Russian forms", () => {
    const forms: [string, string, string] = ["место", "места", "мест"];
    assert.equal(plural(1, forms), "1 место");
    assert.equal(plural(3, forms), "3 места");
    assert.equal(plural(11, forms), "11 мест");
    assert.equal(plural(21, forms), "21 место");
    assert.equal(plural(25, forms), "25 мест");
  });
});
