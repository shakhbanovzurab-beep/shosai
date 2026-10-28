import { describe, expect, it } from "vitest";

import { type CallPerson, mayRemove, principalOf, raisedHands, stageOf } from "./call";

const person = (identity: string, extra: Partial<CallPerson> = {}): CallPerson => ({
  identity,
  name: identity,
  isLocal: false,
  isOwner: false,
  micOn: true,
  cameraOn: true,
  screenOn: false,
  speaking: false,
  lastSpokeAt: 0,
  hand: null,
  ...extra,
});

describe("principalOf", () => {
  it("reads the person or guest behind a session and skips identities Shosai did not mint", () => {
    expect(principalOf("guest-0a1b2c3d4e5f__1a2b3c4d")).toBe("guest-0a1b2c3d4e5f");
    expect(principalOf("EG_recorder")).toBeNull();
    expect(principalOf("guest-0a1b2c3d4e5f__zz")).toBeNull();
  });
});

describe("stageOf", () => {
  it("fits a small call whole and keeps the order people joined in", () => {
    const people = [person("a"), person("b", { speaking: true }), person("c")];
    expect(stageOf(people, new Set()).tiles.map((p) => p.identity)).toEqual(["a", "b", "c"]);
  });

  it("gives a large call's video to the pinned, the screen, the speakers and recent speakers", () => {
    const people = Array.from({ length: 50 }, (_, index) => person(`p${index}`));
    people[40] = person("p40", { lastSpokeAt: 5 });
    people[41] = person("p41", { speaking: true });
    people[42] = person("p42", { screenOn: true });
    people[43] = person("p43", { lastSpokeAt: 9 });
    const stage = stageOf(people, new Set(["p49"]), 4);
    expect(stage.tiles.map((p) => p.identity)).toEqual(["p41", "p42", "p43", "p49"]);
    expect(stage.others).toHaveLength(46);
  });
});

describe("raisedHands and mayRemove", () => {
  it("orders hands by when they went up and lets only the owner remove others", () => {
    const people = [
      person("late", { hand: "2026-10-27T12:05:00Z" }),
      person("early", { hand: "2026-10-27T12:01:00Z" }),
    ];
    expect(raisedHands(people).map((p) => p.identity)).toEqual(["early", "late"]);
    expect(mayRemove("owner", person("x"))).toBe(true);
    expect(mayRemove("owner", person("me", { isLocal: true }))).toBe(false);
    expect(mayRemove("participant", person("x"))).toBe(false);
  });
});
