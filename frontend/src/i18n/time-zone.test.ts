import { afterEach, describe, it } from "vitest";

import { dayIn, daysBetween } from "./calendar-days";
import { cabinetTimeZone, setProfileTimeZone } from "./time-zone";
import assert from "node:assert/strict";

afterEach(() => setProfileTimeZone(null));

describe("cabinet time zone", () => {
  it("takes the profile's zone, and the browser's without one", () => {
    const browser = Intl.DateTimeFormat().resolvedOptions().timeZone;
    assert.equal(cabinetTimeZone(), browser);

    setProfileTimeZone("Europe/Moscow");
    assert.equal(cabinetTimeZone(), "Europe/Moscow");

    setProfileTimeZone(null);
    assert.equal(cabinetTimeZone(), browser);
  });

  it("keeps the browser's zone when the profile names one the browser does not know", () => {
    setProfileTimeZone("Mars/Olympus_Mons");
    assert.equal(cabinetTimeZone(), Intl.DateTimeFormat().resolvedOptions().timeZone);
  });
});

describe("dayIn", () => {
  it("gives a moment's calendar day in the zone", () => {
    const moment = "2026-10-20T21:30:00Z";
    assert.equal(dayIn(moment, "UTC"), "2026-10-20");
    assert.equal(dayIn(moment, "Europe/Moscow"), "2026-10-21");
    assert.equal(dayIn(moment, "America/New_York"), "2026-10-20");
  });
});

describe("daysBetween", () => {
  it("counts whole calendar days, across a month and a daylight-saving change", () => {
    assert.equal(daysBetween("2026-10-20", "2026-10-21"), 1);
    assert.equal(daysBetween("2026-10-21", "2026-10-20"), -1);
    assert.equal(daysBetween("2026-10-30", "2026-11-02"), 3);
  });
});
