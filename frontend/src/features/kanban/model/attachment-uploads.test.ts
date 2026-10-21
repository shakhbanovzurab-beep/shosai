import { describe, expect, it } from "vitest";

import { ATTACHMENT_UPLOAD_MAX } from "../domain/tasks-contract";
import { attachFiles, attachmentRows, dismissRow } from "./attachment-uploads";

describe("attachments on their way", () => {
  it("refuses a file over the limit as a row at once, sending nothing, until it is dismissed", () => {
    const big = { name: "screen-recording.mov", size: ATTACHMENT_UPLOAD_MAX + 1 } as File;
    attachFiles("task-1", [big], null, null);
    const [row] = attachmentRows("task-1");
    expect(row).toMatchObject({ name: "screen-recording.mov", kind: "upload", sent: 0, failure: "upload_too_large" });
    dismissRow("task-1", row.id);
    expect(attachmentRows("task-1")).toEqual([]);
  });
});
