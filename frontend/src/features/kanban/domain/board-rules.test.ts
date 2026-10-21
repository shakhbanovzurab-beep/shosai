import { describe, expect, it } from "vitest";

import { columnSum, heirOf, locate, moveToEdge, placeCard, shiftColumn, sortByPriority } from "./board-rules";
import type { ColumnHead } from "./boards-contract";
import type { Card, Priority } from "./tasks-contract";

const card = (id: string, priority: Priority | null) => ({ id, priority }) as Card;

describe("card order", () => {
  it("places a card in another column and finds it there", () => {
    const next = placeCard({ a: ["1", "2"], b: ["3"] }, "1", "b", 1);
    expect(next).toEqual({ a: ["2"], b: ["3", "1"] });
    expect(locate(next, "1")).toEqual({ columnId: "b", index: 1 });
  });

  it("moves a card to the top or the bottom of its column", () => {
    expect(moveToEdge({ a: ["1", "2", "3"] }, "3", "a", "top").a).toEqual(["3", "1", "2"]);
    expect(moveToEdge({ a: ["1", "2", "3"] }, "1", "a", "bottom").a).toEqual(["2", "3", "1"]);
  });

  it("sorts by priority with the unset last, keeping ties in order", () => {
    const cards = Object.fromEntries(
      [card("n", null), card("l", "low"), card("h1", "high"), card("m", "medium"), card("h2", "high")].map((c) => [
        c.id,
        c,
      ]),
    );
    expect(sortByPriority(["n", "l", "h1", "m", "h2"], cards)).toEqual(["h1", "h2", "m", "l", "n"]);
  });

  it("shifts a column within the board and stays put at the edges", () => {
    expect(shiftColumn(["a", "b", "c"], "b", -1)).toEqual(["b", "a", "c"]);
    expect(shiftColumn(["a", "b", "c"], "c", 1)).toEqual(["a", "b", "c"]);
  });
});

describe("columns", () => {
  const head = (id: string, kind: ColumnHead["kind"]): ColumnHead => ({
    id,
    title: id,
    kind,
    color: null,
    collapsed: false,
  });
  const columns = { a: head("a", "todo"), b: head("b", "in_progress"), c: head("c", "todo"), d: head("d", "done") };

  it("hands a deleted column's cards to the first other column of its kind, or to none", () => {
    expect(heirOf(["a", "b", "c", "d"], columns, "c")).toBe("a");
    expect(heirOf(["a", "b", "c", "d"], columns, "a")).toBe("c");
    expect(heirOf(["a", "b", "c", "d"], columns, "d")).toBeNull();
  });

  it("sums a number field to the cent, skipping cards without a value", () => {
    const cards = {
      x: { values: { est: { number: 0.1 } } },
      y: { values: { est: { number: 0.2 } } },
      z: { values: { other: { number: 5 } } },
    } as unknown as Record<string, Card>;
    expect(columnSum(["x", "y", "z", "missing"], cards, "est")).toBe(0.3);
    expect(columnSum(["z", "missing"], cards, "est")).toBeNull();
  });
});
