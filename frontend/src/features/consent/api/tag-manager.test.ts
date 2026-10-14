import { describe, expect, it } from "vitest";

import { startTagManager, type TagHost, tagManagerUrl, updateTagConsent } from "./tag-manager";

function fakeHost(): TagHost & { scripts: string[] } {
  const scripts: string[] = [];
  return { dataLayer: [], scripts, appendScript: (src) => void scripts.push(src) };
}

// Команды gtag GTM принимает только объектом arguments; в тесте он превращается в массив для сравнения.
function commands(host: TagHost): unknown[] {
  return host.dataLayer.map((entry) =>
    Object.prototype.toString.call(entry) === "[object Arguments]" ? Array.from(entry as ArrayLike<unknown>) : entry,
  );
}

describe("tag manager", () => {
  it("denies every signal before gtm.js loads, without a stored choice", () => {
    const host = fakeHost();

    startTagManager(host, "GTM-MLQW5VGQ", null);

    const [defaults, start] = commands(host);
    expect(defaults).toEqual([
      "consent",
      "default",
      {
        ad_storage: "denied",
        analytics_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        wait_for_update: 500,
      },
    ]);
    expect(start).toMatchObject({ event: "gtm.js" });
    expect(host.scripts).toEqual(["https://www.googletagmanager.com/gtm.js?id=GTM-MLQW5VGQ"]);
  });

  it("pushes gtag commands as an arguments object, which Consent Mode requires", () => {
    const host = fakeHost();

    startTagManager(host, "GTM-MLQW5VGQ", null);

    expect(Object.prototype.toString.call(host.dataLayer[0])).toBe("[object Arguments]");
  });

  it("applies a stored choice before gtm.js and a new one at once", () => {
    const host = fakeHost();

    startTagManager(host, "GTM-MLQW5VGQ", "granted");
    updateTagConsent(host, "denied");

    const [, stored, start, update] = commands(host);
    expect(stored).toEqual(["consent", "update", expect.objectContaining({ analytics_storage: "granted" })]);
    expect(start).toMatchObject({ event: "gtm.js" });
    expect(update).toEqual(["consent", "update", expect.objectContaining({ ad_storage: "denied" })]);
  });

  it("encodes the container id into the script address", () => {
    expect(tagManagerUrl("GTM-A&B")).toBe("https://www.googletagmanager.com/gtm.js?id=GTM-A%26B");
  });
});
