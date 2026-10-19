import { describe, expect, it } from "vitest";

import type { MemoryFact } from "./contract";
import { countByKind, filterFacts, groupByKind, splitFacts } from "./facts";

const fact = (id: string, patch: Partial<MemoryFact> = {}): MemoryFact => ({
  id,
  kind: "preference",
  statement: id,
  status: "active",
  pinned: false,
  source: { kind: "user_statement", title: null },
  created_at: "2026-10-01T00:00:00Z",
  ...patch,
});

describe("the memory page's facts", () => {
  it("keep candidates apart and put pinned facts first, then the newest", () => {
    const { candidates, active } = splitFacts([
      fact("old", { created_at: "2026-09-01T00:00:00Z" }),
      fact("new", { created_at: "2026-10-10T00:00:00Z" }),
      fact("pinned", { pinned: true, created_at: "2026-08-01T00:00:00Z" }),
      fact("ask", { status: "candidate" }),
    ]);

    expect(candidates.map((f) => f.id)).toEqual(["ask"]);
    expect(active.map((f) => f.id)).toEqual(["pinned", "new", "old"]);
  });

  it("count, filter by kind and search by text in any case", () => {
    const facts = [
      fact("Prefers short answers"),
      fact("Works with Lumen", { kind: "relationship" }),
      fact("Ships on Fridays", { kind: "procedure" }),
    ];

    expect(countByKind(facts)).toEqual({ preference: 1, fact: 0, relationship: 1, goal: 0, procedure: 1 });
    expect(filterFacts(facts, "relationship", "", "en").map((f) => f.id)).toEqual(["Works with Lumen"]);
    expect(filterFacts(facts, "all", "  SHORT ", "en").map((f) => f.id)).toEqual(["Prefers short answers"]);
  });

  it("group by kind in a fixed order, without empty groups", () => {
    const groups = groupByKind([fact("a", { kind: "goal" }), fact("b"), fact("c", { kind: "goal" })]);

    expect(groups.map(([kind, items]) => [kind, items.length])).toEqual([
      ["preference", 1],
      ["goal", 2],
    ]);
  });
});
