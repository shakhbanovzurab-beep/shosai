import { describe, expect, it } from "vitest";

import { VOICE_CLOSE, voiceEndOf, voiceFrameOf } from "./voice-wire";

describe("the voice wire", () => {
  it("reads the server's frames it knows", () => {
    expect(voiceFrameOf('{"type":"state","state":"speaking"}')).toEqual({ type: "state", state: "speaking" });
    expect(voiceFrameOf('{"type":"server.shutdown"}')).toEqual({ type: "server.shutdown" });
  });

  it("skips frames it does not know and broken text", () => {
    expect(voiceFrameOf('{"type":"new.kind"}')).toBeNull();
    expect(voiceFrameOf("not json")).toBeNull();
    expect(voiceFrameOf("[1,2]")).toBeNull();
    expect(voiceFrameOf("null")).toBeNull();
  });

  it("tells why a conversation ended by its close code", () => {
    expect(voiceEndOf(VOICE_CLOSE.normal)).toBe("ended");
    expect(voiceEndOf(VOICE_CLOSE.restart)).toBe("reconnect");
    expect(voiceEndOf(VOICE_CLOSE.tryLater)).toBe("reconnect");
    expect(voiceEndOf(VOICE_CLOSE.unauthorized)).toBe("signedOut");
    expect(voiceEndOf(VOICE_CLOSE.minutesUsedUp)).toBe("minutes");
    expect(voiceEndOf(VOICE_CLOSE.minutesUsedUp, "minutes_exhausted")).toBe("minutes");
    expect(voiceEndOf(VOICE_CLOSE.minutesUsedUp, "token_limit")).toBe("tokens");
    expect(voiceEndOf(VOICE_CLOSE.conflict)).toBe("busy");
    expect(voiceEndOf(VOICE_CLOSE.limited)).toBe("limit");
    expect(voiceEndOf(1006)).toBe("failed");
  });
});
