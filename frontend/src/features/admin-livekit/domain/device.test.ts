import { describe, expect, it } from "vitest";

import { deviceLabel } from "./device";

const none = { os: null, os_version: null, client: null, client_version: null, browser: null };

describe("deviceLabel", () => {
  it("names the desktop app with its version and the system", () => {
    const device = { ...none, os: "macos", os_version: "macOS 15.1", client: "desktop", client_version: "2.4.1" };
    expect(deviceLabel(device)).toBe("Leo для macOS 2.4.1 · macOS 15.1");
  });

  it("names the browser of a web client", () => {
    expect(deviceLabel({ ...none, os: "linux", client: "web", browser: "Firefox 143" })).toBe("Firefox 143 · Linux");
  });

  it("keeps an unknown system as declared and says when nothing was declared", () => {
    expect(deviceLabel({ ...none, os: "haiku", client: "desktop" })).toBe("Leo для haiku");
    expect(deviceLabel(none)).toBe("Устройство не указано");
  });
});
