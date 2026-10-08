import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { createApiClient, dataOf } from "./client";
import { ApiError } from "./errors";

const BASE = "http://api.test";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterAll(() => server.close());

describe("createApiClient", () => {
  it("returns the typed body of a success", async () => {
    server.use(http.get(`${BASE}/v1/health`, () => HttpResponse.json({ status: "ok" })));
    await expect(dataOf(createApiClient(BASE).GET("/v1/health"))).resolves.toEqual({ status: "ok" });
  });

  it("sends the interface language", async () => {
    let language: string | null = null;
    server.use(
      http.get(`${BASE}/v1/health`, ({ request }) => {
        language = request.headers.get("accept-language");
        return HttpResponse.json({ status: "ok" });
      }),
    );
    await dataOf(createApiClient(BASE).GET("/v1/health"));
    expect(language).toBe("en");
  });

  it("turns the error envelope into an ApiError with its code and request id", async () => {
    const envelope = { error: { code: "home_unavailable", request_id: "0199a3c2" }, detail: "home_unavailable" };
    server.use(http.get(`${BASE}/v1/health`, () => HttpResponse.json(envelope, { status: 503 })));
    const failure = await dataOf(createApiClient(BASE).GET("/v1/health")).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 503, code: "home_unavailable", requestId: "0199a3c2" });
    expect((failure as ApiError).showsRequestId).toBe(true);
  });
});
