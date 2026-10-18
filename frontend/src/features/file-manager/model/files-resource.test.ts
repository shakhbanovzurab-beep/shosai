import { describe, expect, it } from "vitest";

import type { FileItem, FilesResponse, IndexStatus } from "../domain/contract";
import { indexingPoller } from "./files-resource";

const file = (id: string, status: IndexStatus | null): FileItem => ({
  id,
  name: `${id}.md`,
  kind: "text",
  content_type: "text/markdown",
  size_bytes: 1,
  folder_id: null,
  modified_at: "2026-10-18T00:00:00Z",
  starred: false,
  leo_readable: true,
  leo: status === null ? null : { via: "file", status, progress: 0, chunk_count: null, error: null },
});
const data = (...files: FileItem[]): FilesResponse => ({ folders: [], files });

describe("polling the files", () => {
  it("polls while knowledge indexes a file", () => {
    const busy = indexingPoller(2);
    expect([1, 2, 3, 4].map(() => busy(data(file("a", "embedding"))))).toEqual([true, true, true, true]);
  });

  it("polls a standing queue a few times, again when the queue changes, and not when nothing waits", () => {
    const busy = indexingPoller(2);
    const waiting = data(file("a", "queued"));
    const more = data(file("a", "queued"), file("b", "queued"));

    expect([busy(waiting), busy(waiting), busy(waiting)]).toEqual([true, true, false]);
    expect([busy(more), busy(more), busy(more)]).toEqual([true, true, false]);
    expect(busy(data(file("c", null)))).toBe(false);
  });
});
