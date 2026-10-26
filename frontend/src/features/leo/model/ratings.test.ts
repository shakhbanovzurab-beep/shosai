import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  agentApi: {
    rate: vi.fn<(id: string, rating: string) => Promise<{ rating: string; shared: boolean }>>(),
    unrate: vi.fn<(id: string) => Promise<void>>(),
  },
}));
const toasts = vi.hoisted(() => ({ toast: { error: vi.fn() } }));

vi.mock("../api/agent-api", () => api);
vi.mock("sonner", () => toasts);

const { pressRating } = await import("./ratings");

describe("rating an answer", () => {
  it("rates, takes the same rating back on the second press, and says whether the turn is shared", async () => {
    api.agentApi.rate.mockResolvedValue({ rating: "useful", shared: true });
    api.agentApi.unrate.mockResolvedValue();

    const rated = await pressRating("a1", null, "useful", "failed");
    const taken = await pressRating("a1", "useful", "useful", "failed");

    expect(rated).toEqual({ rating: "useful", shared: true, busy: false });
    expect(taken).toEqual({ rating: null, shared: false, busy: false });
    expect(api.agentApi.rate).toHaveBeenCalledWith("a1", "useful");
    expect(api.agentApi.unrate).toHaveBeenCalledWith("a1");
  });

  it("gives the earlier rating back and says so when the server refuses", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    api.agentApi.rate.mockRejectedValue(new Error("offline"));

    const done = await pressRating("a2", null, "not_useful", "Couldn’t save your rating");

    expect(done).toBeUndefined();
    expect(toasts.toast.error).toHaveBeenCalledWith("Couldn’t save your rating");
  });
});
