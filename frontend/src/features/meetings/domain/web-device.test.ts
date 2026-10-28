import { describe, expect, it } from "vitest";

import { webDevice } from "./web-device";

describe("webDevice", () => {
  it("names the browser with its major version and the system", () => {
    const chrome =
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
    expect(webDevice(chrome)).toEqual({ os: "macos", os_version: null, client: "web", browser: "Chrome 141" });
    const edge = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0 Safari/537.36 Edg/141.0";
    expect(webDevice(edge).browser).toBe("Edge 141");
    expect(webDevice("curl/8.0")).toEqual({ os: null, os_version: null, client: "web", browser: null });
  });
});
