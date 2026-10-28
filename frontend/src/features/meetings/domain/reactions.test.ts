import { describe, expect, it } from "vitest";

import { admitReaction, reactionOfPacket, shownReactions } from "./reactions";

describe("reactions", () => {
  it("admits ten a sender's ten seconds and the next once the window moves", () => {
    let times: number[] = [];
    for (let at = 0; at < 10; at++) times = admitReaction(times, at * 100).times;
    expect(admitReaction(times, 1_000).admitted).toBe(false);
    expect(admitReaction(times, 10_001).admitted).toBe(true);
  });

  it("shows the latest forty for four seconds", () => {
    const shown = Array.from({ length: 50 }, (_, index) => ({
      id: `${index}`,
      emoji: "👍" as const,
      from: "a",
      at: index,
    }));
    expect(shownReactions(shown, 100)).toHaveLength(40);
    expect(shownReactions(shown, 4_100)).toHaveLength(0);
  });

  it("reads only version 1 packets of the six emoji", () => {
    expect(reactionOfPacket({ v: 1, emoji: "🎉" })).toBe("🎉");
    expect(reactionOfPacket({ v: 2, emoji: "🎉" })).toBeNull();
    expect(reactionOfPacket({ v: 1, emoji: "💩" })).toBeNull();
  });
});
