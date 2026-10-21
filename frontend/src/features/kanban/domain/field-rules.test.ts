import { describe, expect, it } from "vitest";

import { cardsWithout, cardsWithValues, clearedBy, fieldDraftProblem, valuesOn } from "./field-rules";
import type { Card } from "./tasks-contract";

const card = (id: string, values: Card["values"]) => ({ id, values }) as Card;

describe("a field's values on the board's cards", () => {
  const cards = {
    a: card("a", { type: { state_id: "bug" }, estimate: { number: 3 } }),
    b: card("b", { type: { state_id: "feature" } }),
    c: card("c", {}),
  };

  it("leave every card when the field leaves the board", () => {
    const next = cardsWithout(cards, "type");
    expect(next.a.values).toEqual({ estimate: { number: 3 } });
    expect(next.b.values).toEqual({});
    expect(next.c).toBe(cards.c);
  });

  it("leave only the cards whose state was removed", () => {
    const next = cardsWithout(cards, "type", (state) => state === "feature");
    expect(next.a.values).toEqual({ estimate: { number: 3 } });
    expect(next.b).toBe(cards.b);
  });

  it("come back to the same cards when taking the field off was refused", () => {
    const kept = valuesOn(cards, "type");
    expect(kept).toEqual({ a: { state_id: "bug" }, b: { state_id: "feature" } });
    const back = cardsWithValues(cardsWithout(cards, "type"), "type", kept);
    expect(back.a.values).toEqual(cards.a.values);
    expect(back.b.values).toEqual(cards.b.values);
    expect(back.c.values).toEqual({});
  });

  it("count the tasks a removal clears", () => {
    expect(clearedBy({ tasks: 6, states: { bug: 1, feature: 4 } }, ["bug", "chore"])).toBe(1);
  });
});

describe("a field draft", () => {
  it("needs a name, and a set needs distinct named states", () => {
    expect(fieldDraftProblem("number", "  ", [])).toBe("name_required");
    expect(fieldDraftProblem("number", "Estimate", [])).toBeNull();
    expect(fieldDraftProblem("states", "Type", [])).toBe("states_required");
    expect(fieldDraftProblem("states", "Type", [{ name: " ", color: "red" }])).toBe("state_name_required");
    expect(
      fieldDraftProblem("states", "Type", [
        { name: "Bug", color: "red" },
        { name: "bug", color: "blue" },
      ]),
    ).toBe("state_names_repeat");
    expect(fieldDraftProblem("states", "Type", [{ name: "Bug", color: "red" }])).toBeNull();
  });
});
