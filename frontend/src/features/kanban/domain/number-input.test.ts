import { describe, expect, it } from "vitest";

import { parseNumberInput } from "./number-input";

describe("a number as people type it", () => {
  it("reads the separators of the person's language", () => {
    expect(parseNumberInput("1,000.5", "en")).toBe(1000.5);
    expect(parseNumberInput("2.5", "en")).toBe(2.5);
    expect(parseNumberInput("1.000,5", "de")).toBe(1000.5);
    expect(parseNumberInput("2,5", "ru")).toBe(2.5);
    expect(parseNumberInput("1 000,75", "ru")).toBe(1000.75);
    expect(parseNumberInput("1\u202f000,5", "fr")).toBe(1000.5);
    expect(parseNumberInput("\u22123", "en")).toBe(-3);
  });

  it("reads digits of other scripts", () => {
    expect(parseNumberInput("٣٫٥", "ar")).toBe(3.5);
    expect(parseNumberInput("۱۲", "en")).toBe(12);
    expect(parseNumberInput("४२", "hi")).toBe(42);
    expect(parseNumberInput("１２", "ja")).toBe(12);
  });

  it("refuses what isn't a number", () => {
    expect(parseNumberInput("abc", "en")).toBeNull();
    expect(parseNumberInput("1.2.3", "en")).toBeNull();
    expect(parseNumberInput("", "en")).toBeNull();
  });
});
