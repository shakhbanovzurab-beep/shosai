import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { uploadQueue } from "./upload-queue";

const target = { folderId: null, leo: false };
const report = () => new File([new Uint8Array(100)], "Report.pdf");
const statuses = () => uploadQueue.rows().map((row) => row.status);

describe("the upload queue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    for (const row of uploadQueue.rows()) uploadQueue.remove(row.id);
    vi.useRealTimers();
  });

  it("follows a file from waiting to done, and lets a done row leave on its own", () => {
    const id = uploadQueue.add(report(), target);
    uploadQueue.start(id);
    uploadQueue.saving(id, "u1");
    uploadQueue.done(id);
    expect(statuses()).toEqual(["done"]);

    vi.advanceTimersByTime(4_000);
    expect(statuses()).toEqual([]);
  });

  it("draws progress at most every 150 ms, not on every event", () => {
    const id = uploadQueue.add(report(), target);
    uploadQueue.start(id);
    uploadQueue.sent(id, 10);
    uploadQueue.sent(id, 40);
    expect(uploadQueue.rows()[0]?.sent).toBe(0);

    vi.advanceTimersByTime(150);
    expect(uploadQueue.rows()[0]?.sent).toBe(40);
  });

  it("stops the upload when its row is removed", () => {
    const id = uploadQueue.add(report(), target);
    const started = uploadQueue.start(id);
    uploadQueue.remove(id);

    expect(started?.signal.aborted).toBe(true);
    expect(uploadQueue.start(id)).toBeNull();
  });

  it("keeps the bytes in the bucket for a retry unless the upload is gone", () => {
    const kept = uploadQueue.add(report(), target);
    uploadQueue.start(kept);
    uploadQueue.saving(kept, "u1");
    uploadQueue.fail(kept, new Error("register"), false);
    const gone = uploadQueue.add(report(), target);
    uploadQueue.start(gone);
    uploadQueue.saving(gone, "u2");
    uploadQueue.fail(gone, new Error("expired"), true);

    expect(uploadQueue.retryOf(kept)?.uploadId).toBe("u1");
    expect(uploadQueue.retryOf(gone)?.uploadId).toBeNull();
  });

  it("clears the finished rows and leaves the ones on their way", () => {
    uploadQueue.refuse(report(), target, "empty");
    const running = uploadQueue.add(report(), target);
    uploadQueue.start(running);
    uploadQueue.clearFinished();

    expect(statuses()).toEqual(["sending"]);
  });
});
