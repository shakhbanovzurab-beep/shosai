import { describe, expect, it } from "vitest";

import { outcomeOf, taintOf } from "./card-labels";

describe("a card's codes in words", () => {
  it("words every label, an outside MCP server's by its name, an unknown one generically", () => {
    expect(taintOf("file:foreign")).toEqual({ key: "fileForeign" });
    expect(taintOf("mcp:linear")).toEqual({ key: "mcp", server: "linear" });
    expect(taintOf("calendar:guest")).toEqual({ key: "other" });
  });

  it("words a known failure code and leaves an unknown one to the status", () => {
    expect(outcomeOf("not_found")).toBe("not_found");
    expect(outcomeOf("executor_lost")).toBe("executor_lost");
    expect(outcomeOf("future_code")).toBeNull();
    expect(outcomeOf(null)).toBeNull();
  });
});
