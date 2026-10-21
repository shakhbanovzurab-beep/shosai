import { beforeEach, describe, expect, it, vi } from "vitest";

const client = vi.hoisted(() => ({ GET: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() }));
vi.mock("@/lib/api/app-client", () => ({ apiClient: client }));

const { shareApi } = await import("./share-api");

const ok = (data: unknown, status = 200) => Promise.resolve({ data, response: new Response(null, { status }) });

const LINK = {
  token: "tok",
  path: "/s/tok",
  show_transcript: true,
  show_names: false,
  allow_comments: true,
  expiry: "7d",
  expires_at: "2026-10-28T10:00:00Z",
};

beforeEach(() => vi.clearAllMocks());

describe("share link API", () => {
  it("reads the server's link in the cabinet's shape, and none when it is off", async () => {
    client.GET.mockReturnValueOnce(ok({ link: LINK })).mockReturnValueOnce(ok({ link: null }));

    expect(await shareApi.getShareLink("m-1")).toEqual({
      link: {
        token: "tok",
        path: "/s/tok",
        settings: { showTranscript: true, showNames: false, allowComments: true, expiry: "7d" },
        expiresAt: "2026-10-28T10:00:00Z",
      },
    });
    expect(await shareApi.getShareLink("m-1")).toEqual({ link: null });
    expect(client.GET).toHaveBeenCalledWith("/v1/notes/{meeting_id}/share-link", {
      params: { path: { meeting_id: "m-1" } },
    });
  });

  it("sends the settings in the server's words and turns the link off with no body back", async () => {
    client.PUT.mockReturnValueOnce(ok({ link: { ...LINK, expiry: "never", expires_at: null } }));
    client.DELETE.mockReturnValueOnce(ok(undefined, 204));

    const saved = await shareApi.saveShareLink("m-1", {
      showTranscript: false,
      showNames: true,
      allowComments: false,
      expiry: "never",
    });

    expect(client.PUT.mock.calls[0]?.[1]).toMatchObject({
      body: { show_transcript: false, show_names: true, allow_comments: false, expiry: "never" },
    });
    expect(saved.link?.expiresAt).toBeNull();
    expect(await shareApi.revokeShareLink("m-1")).toEqual({ link: null });
  });
});
