import { afterEach, describe, expect, it } from "vitest";

import { businessToday, businessZone, businessZoneLabel, setBusinessZone } from "./business-zone";

afterEach(() => setBusinessZone("Europe/Moscow"));

describe("the platform's business zone in the admin panel", () => {
  it("is Moscow until the server names another, labelled МСК", () => {
    expect(businessZone()).toBe("Europe/Moscow");
    expect(businessZoneLabel()).toBe("МСК");

    setBusinessZone("Europe/Berlin");
    expect(businessZone()).toBe("Europe/Berlin");
    expect(businessZoneLabel()).toMatch(/^GMT\+[12]$/);
  });

  it("judges today by the business day: 22:30 UTC on the 31st is already the 1st in Moscow", () => {
    const late = Date.parse("2026-10-31T22:30:00Z");

    expect(businessToday(late)).toBe("2026-11-01");
    setBusinessZone("UTC");
    expect(businessToday(late)).toBe("2026-10-31");
  });
});
