import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { createApiClient } from "./client";
import { type SessionPort, sessionMiddleware } from "./session-middleware";

const BASE = "http://api.test";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterAll(() => server.close());

/** A session whose token turns from "old" to "new" on the first renewal; it counts the renewals. */
function session(renewed: string | null = "new"): SessionPort & { renewals: number } {
  let token: string | null = "old";
  const port = {
    renewals: 0,
    accessToken: () => token,
    async renew(failed: string | null) {
      if (failed !== token) return token;
      port.renewals += 1;
      token = renewed;
      return token;
    },
  };
  return port;
}

function client(port: SessionPort) {
  const api = createApiClient(BASE);
  api.use(sessionMiddleware(port));
  return api;
}

// A /v1/me that only the renewed token opens.
const me = http.get(`${BASE}/v1/me`, ({ request }) =>
  request.headers.get("authorization") === "Bearer new"
    ? HttpResponse.json({ id: "u-1" })
    : HttpResponse.json({ error: { code: "token_expired" } }, { status: 401 }),
);

describe("sessionMiddleware", () => {
  it("renews once and replays the request that met a 401", async () => {
    server.use(me);
    const port = session();
    const { data, response } = await client(port).GET("/v1/me");
    expect(response.status).toBe(200);
    expect(data).toEqual({ id: "u-1" });
    expect(port.renewals).toBe(1);
  });

  it("renews once for requests that fail together", async () => {
    server.use(me);
    const port = session();
    const api = client(port);
    const answers = await Promise.all([api.GET("/v1/me"), api.GET("/v1/me"), api.GET("/v1/me")]);
    expect(answers.map(({ response }) => response.status)).toEqual([200, 200, 200]);
    expect(port.renewals).toBe(1);
  });

  it("returns the 401 when the session has ended", async () => {
    server.use(me);
    const { response } = await client(session(null)).GET("/v1/me");
    expect(response.status).toBe(401);
  });

  it("leaves server errors and sign-in routes alone", async () => {
    let bearer: string | null = "unset";
    server.use(
      http.get(`${BASE}/v1/health`, () => HttpResponse.json({ error: { code: "unavailable" } }, { status: 503 })),
      http.post(`${BASE}/v1/auth/refresh`, ({ request }) => {
        bearer = request.headers.get("authorization");
        return HttpResponse.json({ error: { code: "refresh_missing" } }, { status: 401 });
      }),
    );
    const port = session();
    const api = client(port);
    expect((await api.GET("/v1/health")).response.status).toBe(503);
    expect((await api.POST("/v1/auth/refresh")).response.status).toBe(401);
    expect(bearer).toBeNull();
    expect(port.renewals).toBe(0);
  });

  it("signs the routes of /v1/auth that need a session", async () => {
    let bearer: string | null = null;
    server.use(
      http.post(`${BASE}/v1/auth/desktop/code`, ({ request }) => {
        bearer = request.headers.get("authorization");
        return HttpResponse.json({ code: "c-1", expires_in: 120 });
      }),
    );
    await client(session()).POST("/v1/auth/desktop/code", { body: null });
    expect(bearer).toBe("Bearer old");
  });
});
