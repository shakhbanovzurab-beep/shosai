import { describe, expect, it } from "vitest";

import { credentialsFrom, needsAddress } from "./connector-credentials";

const form =
  (values: Record<string, string>) =>
  (name: string): string =>
    values[name] ?? "";

describe("credentialsFrom", () => {
  it("sends only the key of an app connected by a key", () => {
    const body = credentialsFrom({ id: "affinity", auth: "api_key" }, form({ api_key: " k-1 ", login: "x" }));
    expect(body).toEqual({ api_key: "k-1" });
  });

  it("sends only the hook URL of an app connected by a hook", () => {
    const body = credentialsFrom({ id: "zapier", auth: "webhook" }, form({ webhook_url: "https://hooks.test/1" }));
    expect(body).toEqual({ webhook_url: "https://hooks.test/1" });
  });

  it("sends the login and the app password, and the server only for CalDAV", () => {
    const values = form({ login: "anna@yandex.ru", password: "app-pass", address: "https://dav.test" });
    expect(credentialsFrom({ id: "yandex_calendar", auth: "password" }, values)).toEqual({
      login: "anna@yandex.ru",
      password: "app-pass",
      address: null,
    });
    expect(credentialsFrom({ id: "caldav", auth: "password" }, values).address).toBe("https://dav.test");
    expect(needsAddress({ id: "caldav" })).toBe(true);
  });

  it("turns an empty field into null rather than an empty secret", () => {
    expect(credentialsFrom({ id: "affinity", auth: "api_key" }, form({ api_key: "   " }))).toEqual({ api_key: null });
  });
});
