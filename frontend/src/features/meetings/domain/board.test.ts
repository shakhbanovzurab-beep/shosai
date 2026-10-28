import { describe, expect, it } from "vitest";

import { BOARD_ELEMENTS_MAX, sceneTooLarge } from "./board";

describe("sceneTooLarge", () => {
  it("holds a scene to the server's limits on elements and their bytes", () => {
    expect(sceneTooLarge({ elements: [{ id: "a" }], files: {} })).toBe(false);
    expect(sceneTooLarge({ elements: Array.from({ length: BOARD_ELEMENTS_MAX + 1 }, () => 0), files: {} })).toBe(true);
    expect(sceneTooLarge({ elements: [], files: { big: "x".repeat(9 * 1024 * 1024) } })).toBe(true);
  });
});
