import { ADMIN_PANEL } from "./config";
import { resolveLocale } from "./resolve-locale";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

describe("resolveLocale", () => {
  it("renders the admin panel in Russian whatever the user picked", () => {
    assert.equal(resolveLocale(ADMIN_PANEL, "ar"), "ru");
    assert.equal(resolveLocale(ADMIN_PANEL, undefined), "ru");
  });

  it("follows the language cookie elsewhere", () => {
    assert.equal(resolveLocale(null, "ar"), "ar");
    assert.equal(resolveLocale(undefined, "zh-Hant"), "zh-Hant");
  });

  it("falls back to English for a missing or unknown cookie", () => {
    assert.equal(resolveLocale(null, undefined), "en");
    assert.equal(resolveLocale(null, "xx"), "en");
    assert.equal(resolveLocale(null, ""), "en");
  });

  it("ignores any other panel value", () => {
    assert.equal(resolveLocale("dashboard", "de"), "de");
  });
});
