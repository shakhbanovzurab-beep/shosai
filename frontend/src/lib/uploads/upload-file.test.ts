import { describe, expect, it } from "vitest";

import { type UploadPorts, UploadRejectedError, uploadFile } from "./upload-file";
import type { PartLink } from "./upload-parts";
import { PartFailedError, type UploadAnswer } from "./uploads-api";

const SIZES = [16, 16, 5];

function answer(done: number[], state: UploadAnswer["state"] = "pending", round = 0): UploadAnswer {
  return {
    id: "u1",
    purpose: "file_manager",
    state,
    filename: "Report.pdf",
    content_type: "application/pdf",
    size_bytes: 37,
    expires_at: "2026-10-19T00:00:00Z",
    done_parts: done,
    parts: SIZES.map((size_bytes, index) => ({
      number: index + 1,
      size_bytes,
      url: `/bucket/${index + 1}?round=${round}`,
      headers: {},
      expires_at: "2026-10-18T00:15:00Z",
    })).filter((part) => !done.includes(part.number)),
  };
}

/** A fake API and bucket: `failures` lists, per part, how many PUTs fail before one goes through. */
function ports(failures: Record<number, number> = {}, completed: UploadAnswer["state"] = "ready") {
  const sent: string[] = [];
  const cancelled: string[] = [];
  const left = { ...failures };
  const done: number[] = [];
  let round = 0;
  const fake: UploadPorts = {
    create: async () => answer([]),
    read: async () => answer([...done], "pending", ++round),
    complete: async () => answer([...done], completed),
    cancel: async (id) => void cancelled.push(id),
    put: async (link: PartLink, body: Blob, onSent: (bytes: number) => void) => {
      sent.push(link.url);
      if ((left[link.number] ?? 0) > 0) {
        left[link.number] = (left[link.number] ?? 0) - 1;
        throw new PartFailedError(true);
      }
      onSent(body.size);
      done.push(link.number);
    },
    wait: async () => undefined,
  };
  return { fake, sent, cancelled };
}

const report = new File([new Uint8Array(37)], "Report.pdf", { type: "application/pdf" });

describe("an upload straight to the bucket", () => {
  it("sends every part once and reports the whole file sent", async () => {
    const { fake, sent } = ports();
    const progress: number[] = [];

    const id = await uploadFile(report, fake, (bytes) => progress.push(bytes));

    expect(id).toBe("u1");
    expect(sent.toSorted()).toEqual(["/bucket/1?round=0", "/bucket/2?round=0", "/bucket/3?round=0"]);
    expect(progress.at(-1)).toBe(37);
  });

  it("sends a failed part again with a fresh link, and only that part", async () => {
    const { fake, sent } = ports({ 2: 1 });

    await uploadFile(report, fake, () => undefined);

    expect(sent.filter((url) => url.startsWith("/bucket/2"))).toEqual(["/bucket/2?round=0", "/bucket/2?round=1"]);
    expect(sent.filter((url) => url.startsWith("/bucket/1"))).toEqual(["/bucket/1?round=0"]);
  });

  it("gives up after four tries and cancels, so the reserved bytes come back", async () => {
    const { fake, cancelled } = ports({ 3: 4 });

    await expect(uploadFile(report, fake, () => undefined)).rejects.toBeInstanceOf(PartFailedError);
    expect(cancelled).toEqual(["u1"]);
  });

  it("stops at once when the person cancels: no part is tried again or started, and the upload is cancelled", async () => {
    const { fake, sent, cancelled } = ports();
    const controller = new AbortController();
    const put = fake.put;
    fake.put = async (link, body, onSent, signal) => {
      // Как XMLHttpRequest: отмена обрывает запрос, и он падает.
      controller.abort();
      await put(link, body, onSent, signal);
      throw new PartFailedError(false);
    };

    await expect(uploadFile(report, fake, () => undefined, controller.signal)).rejects.toThrow();
    expect(sent).toEqual(["/bucket/1?round=0"]);
    expect(cancelled).toEqual(["u1"]);
  });

  it("cancels an upload the server rejects as not the size it was told", async () => {
    const { fake, cancelled } = ports({}, "rejected");

    await expect(uploadFile(report, fake, () => undefined)).rejects.toBeInstanceOf(UploadRejectedError);
    expect(cancelled).toEqual(["u1"]);
  });
});
