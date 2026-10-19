import { describe, expect, it } from "vitest";

import { MAX_FILES_PER_UPLOAD, MAX_UPLOAD_BYTES } from "./contract";
import { extensionOf, screenFiles, timeLeft, traySummary, type UploadRow } from "./upload-queue";

const file = (name: string, size = 10) => ({ name, size });

const row = (status: UploadRow["status"], size: number, sent = 0): UploadRow => ({
  id: status,
  name: "a.pdf",
  size,
  sent,
  status,
  leo: false,
  msLeft: null,
  refusal: null,
  error: null,
});

describe("the upload panel", () => {
  it("refuses an empty file, one over the limit and every file past one upload's count", () => {
    const many = Array.from({ length: MAX_FILES_PER_UPLOAD + 1 }, (_, i) => file(`${i}.txt`));
    const { accepted, refused } = screenFiles([file("empty.txt", 0), file("huge.mov", MAX_UPLOAD_BYTES + 1), ...many]);

    expect(accepted).toHaveLength(MAX_FILES_PER_UPLOAD);
    expect(refused.map(({ file: f, refusal }) => [f.name, refusal])).toEqual([
      ["empty.txt", "empty"],
      ["huge.mov", "tooLarge"],
      [`${MAX_FILES_PER_UPLOAD}.txt`, "tooMany"],
    ]);
  });

  it("tells a file Leo can't read by that, before its size", () => {
    const { refused } = screenFiles([file("movie.mov", MAX_UPLOAD_BYTES + 1)], (f) => f.name.endsWith(".pdf"));

    expect(refused.map(({ refusal }) => refusal)).toEqual(["unreadable"]);
  });

  it("guesses the time left from the speed so far, and not in the first second", () => {
    expect(timeLeft(25, 100, 0, 500)).toBeNull();
    expect(timeLeft(0, 100, 0, 5_000)).toBeNull();
    expect(timeLeft(25, 100, 0, 2_000)).toBe(6_000);
    expect(timeLeft(100, 100, 0, 2_000)).toBe(0);
  });

  it("sums the files on their way for the head, apart from the finished ones", () => {
    const rows = [row("sending", 100, 50), row("waiting", 100), row("done", 900, 900), row("failed", 10)];

    expect(traySummary(rows)).toEqual({ active: 2, done: 1, failed: 1, percent: 25 });
    expect(traySummary([])).toEqual({ active: 0, done: 0, failed: 0, percent: 0 });
  });

  it("names a file's type by its extension", () => {
    expect(extensionOf("Q3 report.final.pdf")).toBe("PDF");
    expect(extensionOf(".env")).toBe("");
    expect(extensionOf("README")).toBe("");
  });
});
