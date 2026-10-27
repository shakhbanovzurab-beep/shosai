import { describe, expect, it } from "vitest";

import type { AiModel } from "./contract";
import { candidatesFor, heldByDefaults } from "./roles";

const model = (id: string, changes: Partial<AiModel> = {}): AiModel => ({
  id,
  openrouter_id: `maker/${id}`,
  name: id,
  provider: "Maker",
  context_length: 100_000,
  max_output_tokens: 16_000,
  capabilities: ["text", "vision"],
  price_input_per_m: 1,
  price_output_per_m: 4,
  month_spend: 0,
  month_requests: 0,
  enabled: true,
  is_default: false,
  tier: "standard",
  tier_proposed: null,
  ...changes,
});

describe("candidatesFor", () => {
  it("offers only switched-on standard models that read what the role needs", () => {
    const models = [
      model("seeing"),
      model("blind", { capabilities: ["text"] }),
      model("off", { enabled: false }),
      model("dear", { tier: "frontier" }),
    ];

    expect(candidatesFor(models, true).map((item) => item.id)).toEqual(["seeing"]);
    expect(candidatesFor(models, false).map((item) => item.id)).toEqual(["seeing", "blind"]);
  });
});

describe("heldByDefaults", () => {
  it("counts a fallback as holding its model", () => {
    const defaults = [{ role: "code" as const, model_id: "a", fallback_model_id: "b" }];

    expect(heldByDefaults(defaults, "b")).toBe(true);
    expect(heldByDefaults(defaults, "c")).toBe(false);
  });
});
