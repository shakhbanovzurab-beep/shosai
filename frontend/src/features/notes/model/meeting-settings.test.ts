import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ keepsMeetings: vi.fn(async () => true), keepMeetings: vi.fn() }));
vi.mock("../api/meeting-settings-api", () => ({ meetingSettingsApi: api }));

const { keepingResource, keepMeetings } = await import("./meeting-settings");

const shown = () => {
  const state = keepingResource.getSnapshot();
  return state.status === "ready" ? state.data : state.status;
};

describe("don't keep my meetings", () => {
  it("keeps the server's answer, and moves back when the server refuses", async () => {
    await keepingResource.refresh();
    expect(shown()).toBe(true);

    api.keepMeetings.mockResolvedValueOnce(false);
    await keepMeetings(false);
    expect(api.keepMeetings).toHaveBeenLastCalledWith(false);
    expect(shown()).toBe(false);

    api.keepMeetings.mockRejectedValueOnce(new Error("offline"));
    await expect(keepMeetings(true)).rejects.toThrow("offline");
    expect(shown()).toBe(false);
  });
});
