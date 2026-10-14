import { describe, expect, it } from "vitest";

import { consentSignals, containerIdFrom, decodeConsent, encodeConsent } from "./consent";

describe("consent", () => {
  it("reads back what it stores and nothing of another format", () => {
    expect(decodeConsent(encodeConsent("granted"))).toBe("granted");
    expect(decodeConsent(encodeConsent("denied"))).toBe("denied");
    for (const value of [null, "", "granted", "v0.granted", "v1.maybe"]) expect(decodeConsent(value)).toBeNull();
  });

  it("decides every Consent Mode v2 signal at once", () => {
    expect(consentSignals("denied")).toEqual({
      ad_storage: "denied",
      analytics_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
  });

  it("takes only a container id of GTM's form", () => {
    expect(containerIdFrom("GTM-MLQW5VGQ")).toBe("GTM-MLQW5VGQ");
    expect(containerIdFrom(" GTM-MLQW5VGQ ")).toBe("GTM-MLQW5VGQ");
    for (const value of [undefined, "", "UA-1234", "GTM-", "GTM-abc<script>"])
      expect(containerIdFrom(value)).toBeNull();
  });
});
