import { describe, expect, it } from "vitest";

import { browserTimeZone } from "@/i18n/time-zone";

import { matchesSearch, SHOWN_ZONES, shownZones, timeZoneOptions, zoneClock } from "./time-zone-options";

describe("time zone options", () => {
  it("lists every zone the browser knows with UTC and the browser's own, sorted by name", () => {
    const zones = [...timeZoneOptions("en").keys()];

    expect(zones).toContain("UTC");
    expect(zones).toContain(browserTimeZone());
    expect(zones).toContain("America/New_York");
    expect(zones).toEqual(zones.toSorted());
  });

  it("finds a zone by its readable name and shows its clock with the offset", () => {
    const newYork = timeZoneOptions("en").get("America/New_York");

    expect(newYork?.label).toBe("America/New York");
    expect(newYork?.keywords).toContain("Eastern Time");
    // Между временем и AM/PM ICU ставит то пробел, то узкий неразрывный — \s покрывает оба.
    expect(zoneClock("America/New_York", "en").format(Date.parse("2026-10-20T17:51:00Z"))).toMatch(/^1:51\sPM GMT-4$/);
  });

  it("counts each zone's offset from UTC now", () => {
    const options = timeZoneOptions("ar");
    const offset = (zone: string) => options.get(zone)?.offsetMinutes;

    expect(offset("UTC")).toBe(0);
    expect(offset("Europe/Moscow")).toBe(180);
    expect(offset("Asia/Tokyo")).toBe(540);
    // Node и Chromium перечисляют старые имена Индии и Непала, другие браузеры — новые.
    expect(offset("Asia/Kolkata") ?? offset("Asia/Calcutta")).toBe(330);
    expect(offset("Asia/Kathmandu") ?? offset("Asia/Katmandu")).toBe(345);
  });

  it("builds the list once per language", () => {
    expect(timeZoneOptions("ru")).toBe(timeZoneOptions("ru"));
    // «Москва, стандартное время»: поиск по «Москва» находит пояс по вхождению.
    expect(timeZoneOptions("ru").get("Europe/Moscow")?.keywords.join(" ")).toContain("Москва");
  });

  it("matches a search as a part of a name, not as scattered letters", () => {
    const options = timeZoneOptions("ru");
    const moscow = options.get("Europe/Moscow");
    const chisinau = options.get("Europe/Chisinau");

    expect(moscow && matchesSearch(moscow, "москва")).toBe(true);
    expect(chisinau && matchesSearch(chisinau, "Москва")).toBe(false);
    expect(shownZones(options, "new york", null).zones.map((option) => option.zone)).toEqual(["America/New_York"]);
  });

  it("shows at most 50 rows: the browser's offset without a search, the matches with one", () => {
    const options = timeZoneOptions("en");
    const here = options.get(browserTimeZone())?.offsetMinutes;
    const nearby = shownZones(options, "", "Pacific/Fiji");
    const broad = shownZones(options, "a", null);

    expect(nearby.zones.every((option) => option.offsetMinutes === here || option.zone === "Pacific/Fiji")).toBe(true);
    expect(nearby.zones.map((option) => option.zone)).toContain("Pacific/Fiji");
    expect(nearby.more).toBe(true);
    expect(broad.zones).toHaveLength(SHOWN_ZONES);
    expect(broad.more).toBe(true);
    expect(shownZones(options, "Moscow", null).more).toBe(false);
  });
});
