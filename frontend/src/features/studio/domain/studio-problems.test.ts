import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { numberParam, studioProblemOf } from "./studio-problems";

const refusal = (code: string, params: Record<string, unknown> = {}) => new ApiError(code, 422, code, "req-1", params);

describe("отказы studio", () => {
  it("известный код приходит со своими параметрами", () => {
    const problem = studioProblemOf(refusal("prompt_over_budget", { tokens: 14_691, max: 12_000 }));

    expect(problem).toEqual({ code: "prompt_over_budget", params: { tokens: 14_691, max: 12_000 } });
    expect(problem && numberParam(problem.params, "tokens")).toBe(14_691);
  });

  it("чужой код и не ошибка API — не отказ studio", () => {
    expect(studioProblemOf(refusal("board_full"))).toBeNull();
    expect(studioProblemOf(new Error("offline"))).toBeNull();
  });

  it("недостающий параметр читается нулём, а не NaN", () => {
    const problem = studioProblemOf(refusal("prompt_limit_reached"));

    expect(problem && numberParam(problem.params, "max")).toBe(0);
  });
});
