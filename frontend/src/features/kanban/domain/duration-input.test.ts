import { describe, expect, it } from "vitest";

import { minutesFromInput } from "./duration-input";

describe("a typed duration", () => {
  it("reads hours with a fraction and minutes, in the person's digits and separators", () => {
    expect(minutesFromInput("1,5", "", "ru", 10_000)).toBe(90);
    expect(minutesFromInput("1.5", "", "en", 10_000)).toBe(90);
    expect(minutesFromInput("٢", "٣٠", "ar", 10_000)).toBe(150);
    expect(minutesFromInput("", "45", "en", 10_000)).toBe(45);
  });

  it("clears with both empty and refuses what is not a duration", () => {
    expect(minutesFromInput(" ", "", "en", 10_000)).toBeNull();
    expect(minutesFromInput("two", "", "en", 10_000)).toBeUndefined();
    expect(minutesFromInput("-1", "", "en", 10_000)).toBeUndefined();
    expect(minutesFromInput("200", "", "en", 10_000)).toBeUndefined();
  });
});
