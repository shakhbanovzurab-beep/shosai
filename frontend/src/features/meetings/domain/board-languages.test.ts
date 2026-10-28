import { describe, expect, it } from "vitest";

import { LANGUAGE_CODES } from "@/lib/language";

import { boardLanguage } from "./board-languages";

describe("boardLanguage", () => {
  it("gives the board every language of the cabinet", () => {
    expect(LANGUAGE_CODES.filter((code) => code !== "en" && boardLanguage(code) === "en")).toEqual([]);
    expect(boardLanguage("zh-Hant")).toBe("zh-TW");
  });
});
