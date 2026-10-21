import { beforeEach, describe, expect, it, vi } from "vitest";

import { browserTimeZone, cabinetTimeZone } from "@/i18n/time-zone";
import { ApiError } from "@/lib/api/errors";

import type { Me } from "../domain/session";

const api = vi.hoisted(() => ({
  patchMe: vi.fn<(change: object) => Promise<Me>>(),
  putAvatar: vi.fn(),
  deleteAvatar: vi.fn(),
}));

vi.mock("../api/profile-api", () => api);

const { followBrowserZone, saveTimeZone } = await import("./profile");
const { clearSession, sessionState, updateSession } = await import("./session-store");

const OTHER_ZONE = browserTimeZone() === "Asia/Tokyo" ? "Europe/Lisbon" : "Asia/Tokyo";

const person = (timezone: string | null, timezoneAuto: boolean): Me => ({
  id: "00000000-0000-7000-8000-000000000001",
  email: "person@example.org",
  full_name: "Person",
  display_name: null,
  work_role: null,
  avatar_url: null,
  timezone,
  timezone_auto: timezoneAuto,
  country: "NL",
  language: "en",
  home: "eu",
  consents: { personal_data: true, cross_border: true, marketing: false, improve_models: false, share_location: false },
  created_at: "2026-01-01T00:00:00Z",
});

beforeEach(() => {
  clearSession();
  api.patchMe.mockReset();
});

describe("the profile's time zone", () => {
  it("follows the browser at entry in the automatic mode", async () => {
    const before = person(OTHER_ZONE, true);
    updateSession({ me: before });
    api.patchMe.mockImplementation(async () => ({ ...before, timezone: browserTimeZone() }));

    await followBrowserZone(before);

    expect(api.patchMe).toHaveBeenCalledWith({ timezone: browserTimeZone(), cross_border_warning_confirmed: false });
    expect(sessionState().me?.timezone).toBe(browserTimeZone());
  });

  it("leaves a fixed zone and a zone already equal to the browser's alone", async () => {
    await followBrowserZone(person(OTHER_ZONE, false));
    await followBrowserZone(person(browserTimeZone(), true));

    expect(api.patchMe).not.toHaveBeenCalled();
  });

  it("does not stop the entry when the server refuses the zone", async () => {
    api.patchMe.mockRejectedValue(new ApiError("unknown_timezone", 422, "unknown_timezone"));

    await expect(followBrowserZone(person(OTHER_ZONE, true))).resolves.toBeUndefined();
  });

  it("fixes a picked zone, and the automatic choice saves the browser's", async () => {
    updateSession({ me: person(null, true) });
    api.patchMe.mockImplementation(async (change) => ({ ...person(null, true), ...change }));

    await saveTimeZone(OTHER_ZONE);
    expect(api.patchMe).toHaveBeenLastCalledWith(
      expect.objectContaining({ timezone: OTHER_ZONE, timezone_auto: false }),
    );
    expect(cabinetTimeZone()).toBe(OTHER_ZONE);

    await saveTimeZone(null);
    expect(api.patchMe).toHaveBeenLastCalledWith(
      expect.objectContaining({ timezone: browserTimeZone(), timezone_auto: true }),
    );
    expect(cabinetTimeZone()).toBe(browserTimeZone());
  });
});
