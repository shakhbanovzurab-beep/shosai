import { describe, expect, it } from "vitest";

import { findI18nProblems } from "./check-i18n";

// Каталоги 16 языков, глоссарии и локализованные исходники проверяются в npm test.
describe("i18n", () => {
  it("has every message in every language, by the glossary and the source rules", () => {
    const { problems, messageCount, sourceFileCount } = findI18nProblems();
    expect(problems).toEqual([]);
    expect(messageCount).toBeGreaterThan(0);
    expect(sourceFileCount).toBeGreaterThan(0);
  });
});
