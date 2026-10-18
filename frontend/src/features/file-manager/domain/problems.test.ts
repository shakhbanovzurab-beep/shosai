import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import type { FileFolder, FileItem } from "./contract";
import { isHeld } from "./files";
import { fileProblemOf } from "./problems";

const file = (over: Partial<FileItem>): FileItem => ({
  id: "f",
  name: "Notes.md",
  kind: "text",
  content_type: "text/markdown",
  size_bytes: 10,
  folder_id: "leo",
  modified_at: "2026-10-18T00:00:00Z",
  starred: false,
  leo_readable: true,
  leo: null,
  ...over,
});
const folders: FileFolder[] = [{ id: "leo", name: "Research", updated_at: "2026-10-18T00:00:00Z", leo: true }];

describe("file problems", () => {
  it("knows the files API's codes and the limit they name, and nothing else", () => {
    const limit = new ApiError("leo_limit", 409, "leo_limit", "req", { limit_bytes: 1024 });

    expect(fileProblemOf(limit)).toEqual({ code: "leo_limit", limitBytes: 1024 });
    expect(fileProblemOf(new ApiError("x", 413, "storage_limit"))).toEqual({ code: "storage_limit", limitBytes: null });
    expect(fileProblemOf(new ApiError("x", 500, "internal_error"))).toBeNull();
    expect(fileProblemOf(new Error("network"))).toBeNull();
  });

  it("calls a readable file of a folder Leo reads, yet not used, held over the limit", () => {
    expect(isHeld(file({}), folders)).toBe(true);
    expect(isHeld(file({ leo_readable: false }), folders)).toBe(false);
    expect(isHeld(file({ folder_id: null }), folders)).toBe(false);
    expect(
      isHeld(file({ leo: { via: "folder", status: "indexed", progress: 100, chunk_count: 3, error: null } }), folders),
    ).toBe(false);
  });
});
