import { describe, expect, it } from "vitest";

import { minutesLeft, problemWords, shortensRetention } from "./chat-rules";

describe("chat rules", () => {
  it("words a problem by messenger and channel kind", () => {
    const of = (
      problem: Parameters<typeof problemWords>[0]["problem"],
      messenger: "telegram" | "slack",
      kind = "group" as const,
    ) => problemWords({ problem, messenger, kind });
    expect(of(null, "telegram")).toBeNull();
    expect(of("bot_not_in_chat", "telegram")).toBe("botRemovedGroup");
    expect(problemWords({ problem: "bot_not_in_chat", messenger: "slack", kind: "public_channel" })).toBe(
      "botNotInChannel",
    );
    expect(problemWords({ problem: "bot_not_in_chat", messenger: "slack", kind: "private_channel" })).toBe(
      "botRemovedPrivate",
    );
    expect(of("rights_missing", "telegram")).toBe("rightsMissing");
    expect(of("token_expired", "slack")).toBe("tokenExpired");
  });

  it("asks before a shorter retention only", () => {
    expect(shortensRetention(90, 30)).toBe(true);
    expect(shortensRetention(90, 365)).toBe(false);
  });

  it("counts whole minutes a 30-minute code has left against a minute clock", () => {
    const issued = Date.parse("2026-10-22T10:00:20Z");
    const expires = new Date(issued + 30 * 60_000).toISOString();
    expect(minutesLeft(expires, Date.parse("2026-10-22T10:00:00Z"))).toBe(30);
    expect(minutesLeft(expires, Date.parse("2026-10-22T10:30:00Z"))).toBe(0);
    expect(minutesLeft(expires, Date.parse("2026-10-22T11:00:00Z"))).toBe(0);
  });
});
