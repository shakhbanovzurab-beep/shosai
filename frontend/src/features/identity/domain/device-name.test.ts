import { describe, expect, it } from "vitest";

import { deviceName } from "./device-name";

describe("deviceName", () => {
  it("names the browser and the system", () => {
    expect(
      deviceName(
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/140.0 Safari/537.36",
      ),
    ).toBe("Chrome · Linux");
    expect(
      deviceName(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
      ),
    ).toBe("Safari · macOS");
    expect(
      deviceName(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 Edg/140.0",
      ),
    ).toBe("Edge · Windows");
    expect(
      deviceName(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1",
      ),
    ).toBe("Safari · iOS");
  });

  it("knows the desktop app, under its old name too", () => {
    expect(deviceName("Shosai/1.5.0 (macOS 15.1)")).toBe("Shosai · macOS");
    expect(deviceName("Whisperer/1.4.5 (Windows 11)")).toBe("Shosai · Windows");
  });

  it("gives up on what it does not know", () => {
    expect(deviceName(null)).toBeNull();
    expect(deviceName("curl/8.9")).toBeNull();
  });
});
