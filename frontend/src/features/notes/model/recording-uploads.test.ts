import { describe, it } from "vitest";

import { type RecordingUpload, shownUploads } from "./recording-uploads";
import assert from "node:assert/strict";

const row = (id: string, meetingId: string | null = null): RecordingUpload => ({
  id,
  name: `${id}.wav`,
  size: 10,
  sent: 0,
  failed: null,
  meetingId,
});

describe("shownUploads", () => {
  it("puts the first upload in the large card's slot when the view has one", () => {
    const { lead, others } = shownUploads([row("a"), row("b")], [], true);

    assert.equal(lead?.id, "a");
    assert.deepEqual(
      others.map((upload) => upload.id),
      ["b"],
    );
  });

  it("hides an upload once its meeting is in the library, in the same frame", () => {
    const { lead, others } = shownUploads([row("a", "m1"), row("b")], [{ id: "m1" }], true);

    assert.equal(lead?.id, "b");
    assert.deepEqual(others, []);
  });

  it("keeps every upload in its section where the view has no large card", () => {
    const { lead, others } = shownUploads([row("a"), row("b", "m2")], [{ id: "m1" }], false);

    assert.equal(lead, undefined);
    assert.deepEqual(
      others.map((upload) => upload.id),
      ["a", "b"],
    );
  });
});
