import { describe, expect, it } from "vitest";

import { apiErrorOf, isNotFound } from "./errors";

describe("apiErrorOf", () => {
  it("reads the legacy detail message of the sample API and shipped-client routes", () => {
    const error = apiErrorOf(404, { detail: "Board not found" });
    expect(error.message).toBe("Board not found");
    expect(isNotFound(error)).toBe(true);
    expect(error.showsRequestId).toBe(false);
  });

  it("joins FastAPI validation messages", () => {
    expect(apiErrorOf(422, { detail: [{ msg: "too short" }, { msg: "required" }] }).message).toBe(
      "too short; required",
    );
  });

  it("reads the envelope: code, request id, params and fields", () => {
    const body = {
      error: { code: "rate_limited", request_id: "abc", params: { retry_after_seconds: 3 }, fields: { name: "x" } },
      detail: "rate_limited",
    };
    const error = apiErrorOf(429, body);
    expect(error).toMatchObject({ code: "rate_limited", requestId: "abc", params: { retry_after_seconds: 3 } });
    expect(error.fields).toEqual({ name: "x" });
    // Код без слов в интерфейсе — показать id запроса для поддержки.
    expect(error.showsRequestId).toBe(true);
  });

  it("takes the request id from the header when the body has none, and falls back to the status", () => {
    const error = apiErrorOf(502, null, new Headers({ "x-request-id": "hdr" }));
    expect(error.message).toBe("HTTP 502");
    expect(error.requestId).toBe("hdr");
    expect(error.showsRequestId).toBe(true);
  });
});
