import { describe, expect, it } from "vitest";

import { batchPercent, partRanges } from "./upload-parts";

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

  it("counts a batch's percent over all its bytes, never past a file's size", () => {
    expect(batchPercent([50, 0], [100, 100])).toBe(25);
    expect(batchPercent([150, 100], [100, 100])).toBe(100);
    expect(batchPercent([], [])).toBe(0);
  });
});
