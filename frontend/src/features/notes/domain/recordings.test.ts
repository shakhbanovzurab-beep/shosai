import { describe, it } from "vitest";

import { recordingTitle } from "./recordings";
import assert from "node:assert/strict";

describe("recordingTitle", () => {
  it("names a meeting as the server does: the file's name without its last extension", () => {
    assert.equal(recordingTitle("Созвон с подрядчиком.wav"), "Созвон с подрядчиком");
    assert.equal(recordingTitle("weekly.sync.mp4"), "weekly.sync");
    assert.equal(recordingTitle("notes"), "notes");
    assert.equal(recordingTitle(".hidden"), ".hidden");
  });
});
