import { describe, expect, it } from "vitest";

import { guestName, joinProblemOf, retryable } from "./join";

describe("join", () => {
  it("turns the server's refusals into the page's states", () => {
    expect(joinProblemOf(410, "room_finished")).toBe("room_finished");
    expect(joinProblemOf(429, null)).toBe("rate_limited");
    expect(joinProblemOf(500, "internal")).toBe("unknown");
    expect(retryable("room_finished")).toBe(false);
    expect(retryable("video_unavailable")).toBe(true);
  });

  it("takes a guest name of 1 to 100 characters", () => {
    expect(guestName("  Анна ")).toBe("Анна");
    expect(guestName(" ")).toBeNull();
    expect(guestName("a".repeat(101))).toBeNull();
  });
});
