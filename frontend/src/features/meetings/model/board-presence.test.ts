import { afterEach, describe, expect, it, vi } from "vitest";

import { HELLO_WAIT_MS } from "../domain/board-protocol";
import { BoardPresence } from "./board-presence";

afterEach(() => vi.useRealTimers());

describe("BoardPresence", () => {
  it("lets the lowest identity save, and a newcomer only after hearing from the others", () => {
    vi.useFakeTimers();
    const presence = new BoardPresence(
      () => "b__1",
      (identity) => identity.toUpperCase(),
    );
    expect(presence.saves()).toBe(false);
    presence.open();
    expect(presence.saves()).toBe(false);
    vi.advanceTimersByTime(HELLO_WAIT_MS);
    expect(presence.saves()).toBe(true);
    presence.joined("a__1");
    presence.point("a__1", 3, 4);
    expect(presence.saves()).toBe(false);
    expect(presence.cursors()).toEqual([{ identity: "a__1", name: "A__1", x: 3, y: 4 }]);
    expect(presence.left("a__1")).toBe(true);
    expect(presence.saves()).toBe(true);
    presence.close();
    expect(presence.saves()).toBe(false);
  });
});
