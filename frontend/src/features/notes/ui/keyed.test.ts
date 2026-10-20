import { describe, it } from "vitest";

import { keyed } from "./keyed";
import assert from "node:assert/strict";

describe("keyed", () => {
  it("gives repeated strings different keys and keeps each string's key when the list grows", () => {
    assert.deepEqual(
      keyed(["Anna", "Ivan", "Anna"]).map((item) => item.key),
      ["Anna#0", "Ivan#0", "Anna#1"],
    );
    assert.equal(keyed(["Ivan", "Anna", "Ivan"])[1]?.key, "Anna#0");
  });
});
