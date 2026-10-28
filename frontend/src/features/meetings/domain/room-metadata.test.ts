import { describe, expect, it } from "vitest";

import { roomMetadataOf } from "./room-metadata";

describe("roomMetadataOf", () => {
  it("reads the room, its owner and its marks", () => {
    const text = '{"v":1,"room_id":"r1","owner":"u1","marks":{"notes":true,"recording":false}}';
    expect(roomMetadataOf(text)).toEqual({ roomId: "r1", owner: "u1", marks: { notes: true, recording: false } });
  });

  it("drops another version or a broken body", () => {
    expect(roomMetadataOf('{"v":2,"room_id":"r1","marks":{"notes":true,"recording":false}}')).toBeNull();
    expect(roomMetadataOf("not json")).toBeNull();
    expect(roomMetadataOf(undefined)).toBeNull();
  });
});
