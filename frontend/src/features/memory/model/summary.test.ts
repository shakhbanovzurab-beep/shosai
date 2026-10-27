import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MemoryFact } from "../domain/contract";
import type { MemoryChange } from "../domain/summary-contract";

const api = vi.hoisted(() => ({
  memoryApi: {
    forget: vi.fn<(id: string) => Promise<void>>(),
    restore: vi.fn<(id: string) => Promise<unknown>>(),
    list: vi.fn(),
  },
}));

vi.mock("../api/memory-api", () => api);
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

const { undoChange } = await import("./summary");

const fact = (id: string): MemoryFact => ({
  id,
  kind: "fact",
  statement: id,
  status: "active",
  pinned: false,
  source: { kind: "user_edit", title: null, thread_id: null, message_id: null },
  created_at: "2026-10-27T00:00:00Z",
});

const change = (kind: MemoryChange["change"], id: string, replaced: string | null = null): MemoryChange => ({
  change: kind,
  fact: fact(id),
  replaced_id: replaced,
});

describe("undoing a change of the summary's box", () => {
  beforeEach(() => {
    api.memoryApi.forget.mockReset().mockResolvedValue(undefined);
    api.memoryApi.restore.mockReset().mockResolvedValue({});
  });

  it("forgets a remembered fact, and restores what a correction replaced or a forget ended", async () => {
    expect(await undoChange(change("remembered", "new"), "failed")).toBe(true);
    expect(await undoChange(change("updated", "successor", "old"), "failed")).toBe(true);
    expect(await undoChange(change("forgotten", "gone"), "failed")).toBe(true);

    expect(api.memoryApi.forget.mock.calls).toEqual([["new"]]);
    expect(api.memoryApi.restore.mock.calls).toEqual([["old"], ["gone"]]);
  });

  it("reports a refusal and keeps the change", async () => {
    api.memoryApi.restore.mockRejectedValue(new Error("past the day"));

    expect(await undoChange(change("forgotten", "gone"), "failed")).toBe(false);
  });
});
