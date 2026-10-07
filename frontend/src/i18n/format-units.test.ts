import { formatBytes, formatDuration } from "./format-units";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

describe("formatBytes", () => {
  it("steps through the units in the interface language", () => {
    assert.equal(formatBytes("en", 25 * 1024 * 1024), "25 MB");
    assert.equal(formatBytes("en", 3.25 * 1024 * 1024), "3.3 MB");
    assert.equal(formatBytes("ru", 3.25 * 1024 * 1024), "3,3 МБ");
    assert.equal(formatBytes("en", 48 * 1024), "48 kB");
  });
});

describe("formatDuration", () => {
  it("shows tenths under ten seconds and drops a trailing .0", () => {
    assert.equal(formatDuration("en", 4200), "4.2 sec");
    assert.equal(formatDuration("en", 4000), "4 sec");
    assert.equal(formatDuration("ru", 4200), "4,2 с");
  });

  it("shows minutes and seconds from a minute on, in the language’s own units", () => {
    assert.equal(formatDuration("en", 65_000), "1 min 5 sec");
    assert.equal(formatDuration("ru", 65_000), "1 мин 5 с");
    assert.match(formatDuration("ja", 65_000), /分.*秒/);
  });
});
