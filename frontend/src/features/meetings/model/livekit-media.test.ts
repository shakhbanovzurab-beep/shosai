import { DisconnectReason } from "livekit-client";
import { describe, expect, it } from "vitest";

import { endOf, incoming } from "./livekit-media";

const packet = (body: unknown) => new TextEncoder().encode(JSON.stringify(body));
const CHAT = {
  v: 1,
  id: "m1",
  seq: 1,
  identity: "a__0a1b2c3d",
  author: "A",
  text: "hi",
  sent_at: "2026-10-28T00:00:00Z",
};

describe("the call's data packets", () => {
  it("takes chat only from the server and reactions only from a participant", () => {
    expect(incoming(packet(CHAT), undefined, "chat").chat?.text).toBe("hi");
    expect(incoming(packet(CHAT), "guest-0a1b2c3d4e5f__0a1b2c3d", "chat").chat).toBeNull();
    expect(incoming(packet({ v: 1, emoji: "👏" }), "p__0a1b2c3d", "reaction").reaction).toEqual({
      emoji: "👏",
      from: "p__0a1b2c3d",
    });
    expect(incoming(packet({ v: 1, emoji: "👏" }), undefined, "reaction").reaction).toBeNull();
    expect(incoming(new Uint8Array([0xff]), undefined, "chat").chat).toBeNull();
  });

  it("tells why the call ended for this participant", () => {
    expect(endOf(DisconnectReason.CLIENT_INITIATED)).toBe("left");
    expect(endOf(DisconnectReason.ROOM_DELETED)).toBe("ended");
    expect(endOf(DisconnectReason.PARTICIPANT_REMOVED)).toBe("removed");
    expect(endOf(DisconnectReason.SIGNAL_CLOSE)).toBe("lost");
  });
});
