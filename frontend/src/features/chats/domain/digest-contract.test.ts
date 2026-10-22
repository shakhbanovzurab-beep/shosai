import { describe, expect, it } from "vitest";

import { digestItems, startsBeforeHistory } from "./digest-contract";
import { displayCode } from "./telegram-contract";

describe("digest rules", () => {
  it("knows when a period starts before Shosai has the chat's messages", () => {
    const period = { from: "2026-10-15T00:00:00Z", to: "2026-10-22T00:00:00Z" };
    const coverage = (history_from: string) => ({ history_from, messages_read: 1, truncated: false });
    expect(startsBeforeHistory({ period, coverage: coverage("2026-10-18T09:00:00Z") })).toBe(true);
    expect(startsBeforeHistory({ period, coverage: coverage("2026-10-01T09:00:00Z") })).toBe(false);
  });

  it("lists items section by section", () => {
    const item = (id: string) => ({ id }) as never;
    const ids = digestItems({ decisions: [item("d")], questions: [item("q")], promises: [item("p")] }).map((i) => i.id);
    expect(ids).toEqual(["d", "q", "p"]);
  });

  it("shows a connect code as two groups of four", () => {
    expect(displayCode("K7QM4PZX")).toBe("K7QM-4PZX");
    expect(displayCode("SHORT")).toBe("SHORT");
  });
});
