import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

const api = vi.hoisted(() => ({
  refreshSession: vi.fn<(csrf: string | null) => Promise<{ access_token: string; expires_in: number }>>(),
  readMe: vi.fn(async () => ({ id: "u-1", language: "en" })),
  endSession: vi.fn(async () => undefined),
}));

vi.mock("../api/session-api", () => api);
vi.mock("@/lib/cookie.client", () => ({ readClientCookie: () => "csrf-1" }));

const { renewSession, signOut } = await import("./session");
const { clearSession, sessionState, updateSession } = await import("./session-store");

function tokens(token: string) {
  return { access_token: token, expires_in: 1800 };
}

beforeEach(() => {
  clearSession();
  updateSession({ status: "unknown" });
  api.refreshSession.mockReset();
});

describe("renewSession", () => {
  it("refreshes once for every caller that met the same expired token", async () => {
    api.refreshSession.mockImplementation(async () => tokens("t-2"));
    updateSession({ status: "signed-in", accessToken: "t-1" });

    const renewed = await Promise.all([renewSession("t-1"), renewSession("t-1"), renewSession("t-1")]);

    expect(renewed).toEqual(["t-2", "t-2", "t-2"]);
    expect(api.refreshSession).toHaveBeenCalledTimes(1);
    expect(api.refreshSession).toHaveBeenCalledWith("csrf-1");
  });

  it("takes a token another tab already renewed without refreshing again", async () => {
    updateSession({ status: "signed-in", accessToken: "from-another-tab" });

    await expect(renewSession("t-1")).resolves.toBe("from-another-tab");
    expect(api.refreshSession).not.toHaveBeenCalled();
  });

  it("signs out when the server refuses the refresh", async () => {
    api.refreshSession.mockRejectedValue(new ApiError("expired", 401, "refresh_expired", null));

    await expect(renewSession(null)).resolves.toBeNull();
    expect(sessionState().status).toBe("signed-out");
  });

  it("keeps the session through a server failure", async () => {
    api.refreshSession.mockRejectedValue(new ApiError("unavailable", 503, "home_unavailable", null));
    updateSession({ status: "signed-in", accessToken: "t-1" });

    await expect(renewSession("t-1")).rejects.toBeInstanceOf(ApiError);
    expect(sessionState()).toMatchObject({ status: "signed-in", accessToken: "t-1" });
  });
});

describe("signOut", () => {
  it("forgets the token even when the server could not be told", async () => {
    api.endSession.mockRejectedValueOnce(new TypeError("offline"));
    updateSession({ status: "signed-in", accessToken: "t-1" });

    await expect(signOut()).rejects.toBeInstanceOf(TypeError);
    expect(sessionState()).toMatchObject({ status: "signed-out", accessToken: null });
  });
});
