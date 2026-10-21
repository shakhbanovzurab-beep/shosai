import { describe, expect, it } from "vitest";

import { formatDate, formatDateTime } from "./format";

const MOSCOW = { zone: "Europe/Moscow", label: "МСК" };

describe("admin dates", () => {
  it("show a moment in the business zone with its label", () => {
    const late = "2026-10-31T22:30:00Z";

    expect(formatDateTime(late, MOSCOW)).toMatch(/1 нояб\. 2026 г\., 01:30 МСК$/);
    expect(formatDate(late, MOSCOW)).toBe("1 нояб. 2026 г.");
  });
});
