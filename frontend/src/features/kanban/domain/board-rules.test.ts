import { describe, expect, it } from "vitest";

import { locate, moveToEdge, placeCard, shiftColumn, sortByPriority } from "./board-rules";
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
