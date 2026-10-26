import { describe, expect, it } from "vitest";

import { formatCategory, formatTick, formatValue, seriesColor, seriesConfig } from "./chart-values";

// Intl разделяет разряды и «тыс.» неразрывными пробелами.
const plain = (text: string) => text.replace(/\s/gu, " ");

describe("chart values", () => {
  it("writes numbers the Russian way and an empty cell as a dash", () => {
    expect(plain(formatValue(1234.5))).toBe("1 234,5");
    expect(formatValue(null)).toBe("—");
    expect(formatValue(undefined)).toBe("—");
    expect(formatValue("EU")).toBe("EU");
  });

  it("names a day on the x axis and leaves other categories as they are", () => {
    expect(formatCategory("2026-10-26")).toBe("26 окт.");
    expect(formatCategory("openai/gpt-5")).toBe("openai/gpt-5");
    expect(formatCategory(7)).toBe("7");
  });

  it("compacts the value axis", () => {
    expect(plain(formatTick(1200))).toBe("1,2 тыс.");
    expect(formatTick(0)).toBe("0");
  });

  it("colours series by their place, never cycling", () => {
    expect(seriesColor(0)).toBe("var(--chart-1)");
    expect(seriesColor(5)).toBe("var(--muted-foreground)");
    expect(seriesConfig([{ key: "useful", label: "Полезно" }])).toEqual({
      useful: { label: "Полезно", color: "var(--chart-1)" },
    });
  });
});
