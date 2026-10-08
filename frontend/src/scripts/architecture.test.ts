import { describe, expect, it } from "vitest";

import { findArchitectureProblems } from "./architecture/check";

// Правила структуры кабинета — часть npm test, а не отдельная команда.
describe("architecture", () => {
  it("keeps the slice rules, the 200-line limit and no barrel files", () => {
    expect(findArchitectureProblems()).toEqual([]);
  });
});
