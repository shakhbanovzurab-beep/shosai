import { describe, expect, it } from "vitest";

import type { AiModel } from "./contract";
import { compare } from "./models-sort";

const priced = (id: string, price: number | null) => ({ id, price_output_per_m: price }) as AiModel;

describe("compare", () => {
  it("keeps a model without a price last in either direction", () => {
    const models = [priced("none", null), priced("cheap", 1), priced("dear", 9)];
    const by = (desc: boolean) =>
      models.toSorted((a, b) => compare(a, b, { key: "price_output_per_m", desc })).map((model) => model.id);

    expect(by(false)).toEqual(["cheap", "dear", "none"]);
    expect(by(true)).toEqual(["dear", "cheap", "none"]);
  });
});
