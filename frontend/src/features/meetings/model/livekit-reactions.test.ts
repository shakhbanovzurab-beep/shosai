import { afterEach, describe, expect, it, vi } from "vitest";

import type { ShownReaction } from "../domain/reactions";
import { ReactionDesk } from "./livekit-reactions";

afterEach(() => vi.useRealTimers());

describe("ReactionDesk", () => {
  it("shows ten of one sender's flood, sends ten of one's own, and clears them after four seconds", () => {
    vi.useFakeTimers();
    let shown: ShownReaction[] = [];
    const desk = new ReactionDesk((next) => {
      shown = next;
    });
    for (let i = 0; i < 15; i++) desk.receive("🎉", "flooder");
    expect(shown).toHaveLength(10);
    const sent = Array.from({ length: 12 }, () => desk.send("👍", "me"));
    expect(sent.filter((packet) => packet !== null)).toHaveLength(10);
    vi.advanceTimersByTime(4_200);
    expect(shown).toHaveLength(0);
  });
});
