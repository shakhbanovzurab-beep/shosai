import { describe, it } from "vitest";

import { voiceOf } from "./meeting-page";
import assert from "node:assert/strict";

describe("voiceOf", () => {
  it("names nobody when the line has no voice", () => {
    assert.deepEqual(voiceOf(null, []), { kind: "unknown" });
  });

  it("takes voice 0 of a live meeting as the owner's, and numbers the rest from 1", () => {
    assert.deepEqual(voiceOf(0, []), { kind: "owner" });
    assert.deepEqual(voiceOf(2, []), { kind: "number", n: 3 });
  });

  it("finds the owner of a recording by the speaker's role", () => {
    const speakers = [
      { idx: 0, role: "speaker", talkMs: 1_000 },
      { idx: 1, role: "owner", talkMs: 2_000 },
    ];

    assert.deepEqual(voiceOf(1, speakers), { kind: "owner" });
    assert.deepEqual(voiceOf(0, speakers), { kind: "number", n: 1 });
  });

  it("numbers every voice of a recording where the owner wasn't recognised", () => {
    const speakers = [{ idx: 0, role: "speaker", talkMs: 1_000 }];

    assert.deepEqual(voiceOf(0, speakers), { kind: "number", n: 1 });
  });
});
