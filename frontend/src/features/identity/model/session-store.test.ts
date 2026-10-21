import { afterEach, describe, expect, it } from "vitest";

import { cabinetTimeZone } from "@/i18n/time-zone";

import type { Me } from "../domain/session";
import { clearSession, updateSession } from "./session-store";

const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

const person = (timezone: string | null, timezoneAuto = false): Me => ({
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

afterEach(() => clearSession());

describe("session store", () => {
  it("gives the cabinet the zone the person fixed, and the browser's back on sign-out", () => {
    updateSession({ me: person("Asia/Tokyo") });
    expect(cabinetTimeZone()).toBe("Asia/Tokyo");

    clearSession();
    expect(cabinetTimeZone()).toBe(browserZone);
  });

  it("keeps the browser's zone in the automatic mode and for a profile without one", () => {
    updateSession({ me: person("Asia/Tokyo", true) });
    expect(cabinetTimeZone()).toBe(browserZone);

    updateSession({ me: person(null) });
    expect(cabinetTimeZone()).toBe(browserZone);
  });
});
