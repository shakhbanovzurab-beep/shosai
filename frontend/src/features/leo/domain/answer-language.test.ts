import { describe, it } from "vitest";

import { answerLanguage } from "./answer-language";
import assert from "node:assert/strict";

describe("answerLanguage", () => {
  it("follows the interface language when the setting is auto", () => {
    assert.equal(answerLanguage("auto", "ja"), "ja");
  });

  it("follows the interface language before settings have loaded", () => {
    assert.equal(answerLanguage(undefined, "ar"), "ar");
  });

  it("uses the language chosen in Settings › Leo over the interface language", () => {
    assert.equal(answerLanguage("de", "ru"), "de");
    assert.equal(answerLanguage("zh-Hant", "en"), "zh-Hant");
  });

  it("ignores a value that is not an interface language", () => {
    assert.equal(answerLanguage("klingon", "fr"), "fr");
  });
});
