import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { problemMessage, problemText } from "./problems";

describe("problemText", () => {
  it("words studio's codes for the admin and leaves unknown ones to the caller", () => {
    expect(problemText("model_is_default")).toContain("умолчание");
    expect(problemText("management_key_missing")).toContain("OPENROUTER_MANAGEMENT_KEY");
    expect(problemText("something_new")).toBeNull();
    expect(problemText(null)).toBeNull();
  });
});

describe("problemMessage", () => {
  it("prefers the admin's words, then the server's message", () => {
    expect(problemMessage(new ApiError("x", 409, "model_already_listed"))).toBe("Эта модель уже в каталоге.");
    expect(problemMessage(new ApiError("Сервер упал", 500, "internal"))).toBe("Сервер упал");
  });
});
