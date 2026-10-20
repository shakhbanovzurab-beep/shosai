import { describe, expect, it } from "vitest";

import { partRanges } from "./upload-parts";

describe("upload parts", () => {
  it("lays the parts end to end by their numbers, whatever order they come in", () => {
    const ranges = partRanges([
      { number: 3, size_bytes: 5 },
      { number: 1, size_bytes: 16 },
      { number: 2, size_bytes: 16 },
    ]);

    expect([...ranges.entries()]).toEqual([
      [1, [0, 16]],
      [2, [16, 32]],
      [3, [32, 37]],
    ]);
  });
});
