import { describe, expect, it } from "vitest";

import { appliedText, changeIndexes, type DiffSegment, segmentKeys } from "./proposals";
import { citedSentences, quoteParts } from "./sources";

describe("a cited answer", () => {
  it("gives each sentence its markers, also a marker written after the full stop", () => {
    const sentences = citedSentences(
      "Jonas agreed to €18 per seat [1]. Billing starts in March. [2][9] Done.",
      2,
      "en",
    );

    expect(sentences).toEqual([
      { text: "Jonas agreed to €18 per seat. ", cites: [1] },
      { text: "Billing starts in March. ", cites: [2] },
      { text: "Done.", cites: [] },
    ]);
  });

  it("marks the words of a quote that back the answer, whatever their case", () => {
    expect(quoteParts("We sign at Eighteen euros per seat.", ["eighteen euros"])).toEqual([
      { text: "We sign at ", at: 0, lit: false },
      { text: "Eighteen euros", at: 11, lit: true },
      { text: " per seat.", at: 25, lit: false },
    ]);
    expect(quoteParts("No highlight.", [])).toEqual([{ text: "No highlight.", at: 0, lit: false }]);
  });
});

describe("a suggested edit", () => {
  const segments: DiffSegment[] = [
    { type: "equal", text: "We " },
    { type: "change", remove: "will be able to", insert: "can" },
    { type: "equal", text: " ship " },
    { type: "change", remove: "at the end of", insert: "by" },
    { type: "equal", text: " November." },
  ];

  it("applies only the changes the person took", () => {
    expect(changeIndexes(segments)).toEqual([1, 3]);
    expect(appliedText(segments, new Set([1]))).toBe("We can ship at the end of November.");
    expect(appliedText(segments, new Set([1, 3]))).toBe("We can ship by November.");
  });

  it("keys every segment by its place in the original text", () => {
    const keys = segmentKeys([{ type: "change", remove: "", insert: "Now " }, ...segments]);

    expect(keys).toEqual(["change:0", "equal:0", "change:3", "equal:18", "change:24", "equal:37"]);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
