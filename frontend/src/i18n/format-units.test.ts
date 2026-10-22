import { describe, it } from "vitest";

import { formatBytes, formatDuration, formatSpan } from "./format-units";
import assert from "node:assert/strict";

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

describe("formatSpan", () => {
  it("shows the two largest parts down to the minute, in the language’s words", () => {
    assert.equal(formatSpan("en", (2 * 60 + 15) * 60_000 + 59_000), "2 hr, 15 min");
    assert.equal(formatSpan("ru", (3 * 24 + 4) * 3_600_000 + 7 * 60_000), "3 дн. 4 ч");
    assert.equal(formatSpan("en", 3_600_000 + 30_000), "1 hr");
    assert.equal(formatSpan("en", 0), "0 min");
    assert.equal(formatSpan("en", -20 * 60_000), "20 min");
    assert.equal(formatSpan("en", 65_000, "second"), "1 min, 5 sec");
  });

  it("falls back to units and a list where Intl.DurationFormat is missing", () => {
    const original = Intl.DurationFormat;
    Reflect.deleteProperty(Intl, "DurationFormat");
    try {
      assert.equal(formatSpan("ru", (2 * 60 + 15) * 60_000), "2 ч 15 мин");
    } finally {
      Object.assign(Intl, { DurationFormat: original });
    }
  });
});
