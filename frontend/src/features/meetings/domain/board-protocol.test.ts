import { describe, expect, it } from "vitest";

import {
  boardMessageOf,
  boardPacket,
  changedSince,
  cursorOf,
  cursorPacket,
  filesSince,
  savesAmong,
  versionSum,
} from "./board-protocol";

const element = (id: string, version: number) => ({ id, version, type: "rectangle" });
const image = { id: "img", mimeType: "image/png", dataURL: "data:image/png;base64,AA" };

describe("board messages", () => {
  it("round-trip with the protocol's version", () => {
    for (const message of [
      { kind: "hello" as const },
      { kind: "saved" as const, version: 3 },
      { kind: "patch" as const, elements: [element("a", 2)], files: [image] },
    ])
      expect(boardMessageOf(boardPacket(message))).toEqual(message);
  });

  it("drop another version, broken JSON and unknown kinds", () => {
    expect(boardMessageOf(JSON.stringify({ v: 2, kind: "hello" }))).toBeNull();
    expect(boardMessageOf("{")).toBeNull();
    expect(boardMessageOf(JSON.stringify({ v: 1, kind: "wipe" }))).toBeNull();
    expect(boardMessageOf(JSON.stringify({ v: 1, kind: "saved", version: "3" }))).toBeNull();
  });

  it("keep only elements with an id and a version, and images as data URLs", () => {
    const raw = JSON.stringify({
      v: 1,
      kind: "scene",
      elements: [element("a", 1), { id: "", version: 1 }, { id: "b" }, "x"],
      files: [image, { ...image, id: "far", dataURL: "https://example.com/a.png" }],
    });
    expect(boardMessageOf(raw)).toEqual({ kind: "scene", elements: [element("a", 1)], files: [image] });
  });
});

describe("cursors", () => {
  it("carry finite scene coordinates only", () => {
    expect(cursorOf(cursorPacket(12.5, -3))).toEqual({ x: 12.5, y: -3 });
    expect(cursorOf(new TextEncoder().encode(JSON.stringify({ v: 1, x: "1", y: 2 })))).toBeNull();
    expect(cursorOf(new TextEncoder().encode("nope"))).toBeNull();
  });
});

describe("the saver", () => {
  it("is the lowest identity among those with the board open", () => {
    expect(savesAmong("b__1", ["c__1", "d__1"])).toBe(true);
    expect(savesAmong("b__1", ["a__1", "c__1"])).toBe(false);
    expect(savesAmong("b__1", [])).toBe(true);
  });
});

describe("what goes in a patch", () => {
  it("is every element at a version peers have not seen and every image not sent", () => {
    const sent = new Map([
      ["a", 1],
      ["b", 2],
    ]);
    expect(changedSince([element("a", 1), element("b", 3), element("c", 1)], sent)).toEqual([
      element("b", 3),
      element("c", 1),
    ]);
    expect(filesSince({ img: image, old: { ...image, id: "old" } }, new Set(["old"]))).toEqual([image]);
  });

  it("tells a changed scene from the loaded one by its versions", () => {
    expect(versionSum([element("a", 2), element("b", 3), { id: "c" }])).toBe(5);
  });
});
