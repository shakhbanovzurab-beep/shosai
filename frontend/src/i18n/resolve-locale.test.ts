import { describe, it } from "vitest";

import { resolveLocale } from "./resolve-locale";
import assert from "node:assert/strict";

describe("resolveLocale", () => {
  it("shows the admin panel in Russian whatever the user picked", () => {
    assert.equal(resolveLocale("/admin/dashboard", "ar"), "ru");
    assert.equal(resolveLocale("/admin", undefined), "ru");
  });

  it("follows the language cookie elsewhere", () => {
    assert.equal(resolveLocale("/app/notes", "ar"), "ar");
    assert.equal(resolveLocale("/app", "zh-Hant"), "zh-Hant");
    assert.equal(resolveLocale("/administrator", "de"), "de");
  });

  it("falls back to English for a missing or unknown cookie", () => {
    assert.equal(resolveLocale("/app", undefined), "en");
    assert.equal(resolveLocale("/app", "xx"), "en");
    assert.equal(resolveLocale("/app", ""), "en");
  });
});
