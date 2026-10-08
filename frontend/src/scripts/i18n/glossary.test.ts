import { describe, it } from "vitest";

import { checkLanguageGlossary, readLanguageGlossary, readStyleGuide, readTermList } from "./glossary";
import assert from "node:assert/strict";

const GUIDE = `# Guide

## Do not translate

- \`Leo\`
- \`GPT Astra\`

## Typography by language

| Code | Address the user | Quotes | Not allowed | Notes |
| --- | --- | --- | --- | --- |
| ru | вы | «…» | \`"\` \`”\` | ё |
| ar | neutral | «…» | \`,\` \`?\` | |
`;

const LANGUAGE = `# Glossary: Русский (ru)

## Terms

| English | Use | Avoid | Note |
| --- | --- | --- | --- |
| workspace | пространство | воркспейс, рабочая область | |
| Save | Сохранить | — | |

## Same as English

- (none)
`;

describe("glossary", () => {
  it("reads the do-not-translate list and the characters each language doesn't use", () => {
    const guide = readStyleGuide(GUIDE);
    assert.deepEqual(guide.doNotTranslate, ["Leo", "GPT Astra"]);
    assert.deepEqual(guide.notAllowed.get("ru"), ['"', "”"]);
    assert.deepEqual(guide.notAllowed.get("ar"), [",", "?"]);
  });

  it("reads a language's terms, avoided words and same-as-English list", () => {
    const glossary = readLanguageGlossary(LANGUAGE);
    assert.deepEqual(glossary.terms, [
      { english: "workspace", use: "пространство", avoid: ["воркспейс", "рабочая область"] },
      { english: "Save", use: "Сохранить", avoid: [] },
    ]);
    assert.deepEqual(glossary.sameAsEnglish, []);
  });

  it("checks a language glossary covers the term list", () => {
    const terms = readTermList(
      "| Term | Area | Meaning |\n| --- | --- | --- |\n| workspace | x | y |\n| Cancel | x | y |",
    );
    assert.deepEqual(checkLanguageGlossary(readLanguageGlossary(LANGUAGE), terms), [
      "lacks the term “Cancel”",
      "has “Save”, which terms.md doesn’t",
    ]);
  });
});
