import { describe, expect, it } from "vitest";

import { lowContrast, themeModes } from "./theme/chart-contrast";

// Цвета графиков читаются на фоне и карточке в каждой теме: порог закреплён тестом, а не памятью.
describe("chart colours", () => {
  it("covers the default theme and every preset in both modes", () => {
    expect(themeModes().map((mode) => mode.name)).toEqual([
      "default light",
      "default dark",
      "brutalist light",
      "brutalist dark",
      "soft-pop light",
      "soft-pop dark",
      "tangerine light",
      "tangerine dark",
    ]);
  });

  it("keeps every --chart-* at 3:1 or more against the background and the card", () => {
    expect(lowContrast()).toEqual([]);
  });
});
