import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { signInProblem } from "./problems";

describe("signInProblem", () => {
  it("names a wrong login without telling which part was wrong", () => {
    expect(signInProblem(new ApiError("x", 401, "invalid_credentials"))).toBe("Неверный логин или пароль.");
  });

  it("rounds the wait up to whole minutes", () => {
    const limited = new ApiError("x", 429, "rate_limited", null, { retry_after_seconds: 61 });
    expect(signInProblem(limited)).toBe("Слишком много попыток. Повторите через 2 мин.");
  });

  it("shows the request id of an unknown failure and a network problem without one", () => {
    expect(signInProblem(new ApiError("x", 500, "internal", "r-1"))).toContain("r-1");
    expect(signInProblem(new TypeError("fetch failed"))).toContain("Нет связи");
  });
});
