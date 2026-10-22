import { describe, expect, it } from "vitest";

import { type BoardFilter, NO_FILTER, UNASSIGNED } from "./filter-contract";
import { cardMatches, dueBucket, forVisible, isFiltering } from "./filter-rules";
import { filterFromSearch, searchWithFilter } from "./filter-url";
import { placeAmongVisible, visibleIds } from "./filtered-move";
import type { Card } from "./tasks-contract";

const TODAY = "2026-10-21";
const card = (fields: Partial<Card>): Card =>
  ({
    id: "c",
    title: "Card",
    status: "todo",
    priority: null,
    due_on: null,
    assignee: null,
    recurring: false,
    values: {},
    ...fields,
  }) as Card;
const with_ = (patch: Partial<BoardFilter>): BoardFilter => ({ ...NO_FILTER, ...patch });
const matches = (c: Card, f: BoardFilter) => cardMatches(c, f, TODAY);

describe("the deadline buckets", () => {
  it("count from the person's today, and a done task is never overdue", () => {
    expect(dueBucket({ due_on: "2026-10-20", status: "todo" }, TODAY)).toBe("overdue");
    expect(dueBucket({ due_on: "2026-10-20", status: "done" }, TODAY)).toBeNull();
    expect(dueBucket({ due_on: TODAY, status: "todo" }, TODAY)).toBe("today");
    expect(dueBucket({ due_on: "2026-10-27", status: "todo" }, TODAY)).toBe("week");
    expect(dueBucket({ due_on: "2026-10-28", status: "todo" }, TODAY)).toBe("later");
    expect(dueBucket({ due_on: null, status: "todo" }, TODAY)).toBe("none");
  });
});

describe("a card under a filter", () => {
  it("takes choices within a field as alternatives, and fields together", () => {
    const high = card({ priority: "high", assignee: { user_id: null, name: "Maya" } });
    expect(matches(high, with_({ priority: ["high", "low"] }))).toBe(true);
    expect(matches(high, with_({ priority: ["high"], assignee: ["Maya"] }))).toBe(true);
    expect(matches(high, with_({ priority: ["high"], assignee: [UNASSIGNED] }))).toBe(false);
    expect(matches(card({}), with_({ priority: ["none"], assignee: [UNASSIGNED] }))).toBe(true);
  });

  it("filters states with an empty choice, numbers by kind and range, and texts by contains", () => {
    const bug = card({ values: { type: { state_id: "bug" }, est: { number: 3 }, notes: { text: "Northwind" } } });
    expect(matches(bug, with_({ states: { type: ["bug", "~empty"] } }))).toBe(true);
    expect(matches(card({}), with_({ states: { type: ["~empty"] } }))).toBe(true);
    expect(matches(bug, with_({ numbers: { est: { mode: "range", from: 2, to: 3 } } }))).toBe(true);
    expect(matches(bug, with_({ numbers: { est: { mode: "range", from: 4, to: null } } }))).toBe(false);
    expect(matches(bug, with_({ numbers: { est: { mode: "empty" } } }))).toBe(false);
    expect(matches(bug, with_({ texts: { notes: "north" } }))).toBe(true);
  });

  it("forgets the filter of a field the board hides", () => {
    const f = with_({ priority: ["high"], states: { type: ["bug"] } });
    expect(isFiltering(forVisible(f, new Set(["assignee"])))).toBe(false);
    expect(forVisible(f, new Set(["priority", "type"]))).toEqual(f);
  });
});

describe("the filter in the address", () => {
  it("goes there and back, keeping the board and the open task", () => {
    const f = with_({
      assignee: ["Maya Chen", UNASSIGNED],
      due: ["overdue", "today"],
      priority: ["high"],
      repeat: ["no"],
      states: { "st-type": ["type-bug", "~empty"] },
      numbers: { est: { mode: "range", from: 1, to: null } },
      texts: { cust: "north" },
    });
    const params = searchWithFilter(new URLSearchParams("board=work&task=t1&due=later"), f);
    expect(params.get("board")).toBe("work");
    expect(params.get("task")).toBe("t1");
    expect(filterFromSearch(params)).toEqual(f);
  });

  it("drops what it does not know", () => {
    expect(
      filterFromSearch(new URLSearchParams("due=yesterday&priority=urgent&number.x=range:a:5&repeat=maybe")),
    ).toEqual(with_({ numbers: { x: { mode: "range", from: null, to: 5 } } }));
  });
});

describe("a move under a filter", () => {
  const full = { todo: ["a", "h1", "b", "h2", "c"], done: ["d", "h3"] };
  const shown = new Set(["a", "b", "c", "d"]);

  it("puts the card right after the visible card above it, hidden ones staying put", () => {
    const visible = visibleIds(full, shown);
    expect(visible).toEqual({ todo: ["a", "b", "c"], done: ["d"] });
    expect(placeAmongVisible(full, { todo: ["a", "c", "b"], done: ["d"] }, "c")).toEqual({
      todo: ["a", "c", "h1", "b", "h2"],
      done: ["d", "h3"],
    });
    expect(placeAmongVisible(full, { todo: ["b", "c"], done: ["d", "a"] }, "a")).toEqual({
      todo: ["h1", "b", "h2", "c"],
      done: ["d", "a", "h3"],
    });
  });

  it("puts it at the top when no visible card is above it", () => {
    expect(placeAmongVisible(full, { todo: ["a", "b", "c"], done: ["d"] }, "d").done).toEqual(["d", "h3"]);
    expect(placeAmongVisible(full, { todo: ["d", "a", "b", "c"], done: [] }, "d").todo[0]).toBe("d");
  });
});
