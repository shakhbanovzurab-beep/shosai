import { describe, expect, it } from "vitest";

import { chatOfPacket, mergeChat, sendableText, unreadCount } from "./chat-log";

const message = (seq: number, identity = "a") => ({
  id: `m${seq}`,
  seq,
  identity,
  author: identity,
  text: `#${seq}`,
  sentAt: "2026-10-27T12:00:00Z",
});

describe("chat log", () => {
  it("keeps one message per id in seq order, whatever order they arrive in", () => {
    const log = mergeChat([message(1)], [message(3), message(2), message(3)]);
    expect(log.map((m) => m.seq)).toEqual([1, 2, 3]);
  });

  it("counts others' messages after the one read", () => {
    const log = [message(1, "me"), message(2, "b"), message(3, "b")];
    expect(unreadCount(log, 2, "me")).toBe(1);
  });

  it("sends trimmed text of 1 to 2 000 characters and reads only the server's packets", () => {
    expect(sendableText("  hi ")).toBe("hi");
    expect(sendableText("   ")).toBeNull();
    expect(sendableText("x".repeat(2_001))).toBeNull();
    const packet = { v: 1, id: "m1", seq: 1, identity: "a", author: "A", text: "hi", sent_at: "2026-10-27T12:00:00Z" };
    expect(chatOfPacket(packet)?.text).toBe("hi");
    expect(chatOfPacket({ ...packet, seq: "1" })).toBeNull();
  });
});
