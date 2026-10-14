import { describe, expect, it } from "vitest";

import { desktopRequestOf, desktopReturnUrl } from "./desktop-link";

describe("desktopRequestOf", () => {
  it("reads the state and the optional PKCE challenge", () => {
    expect(desktopRequestOf(new URLSearchParams("state=s-1&code_challenge=c-1"))).toEqual({
      state: "s-1",
      codeChallenge: "c-1",
    });
    expect(desktopRequestOf(new URLSearchParams("state=s-1"))).toEqual({ state: "s-1", codeChallenge: null });
  });

  it("refuses a request without a state", () => {
    expect(desktopRequestOf(new URLSearchParams("code_challenge=c-1"))).toBeNull();
  });
});

it("sends the code back to the app with the same state", () => {
  expect(desktopReturnUrl("a b", "s&1")).toBe("shosai://auth?code=a%20b&state=s%261");
});
