import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FactsPage, MemoryFact } from "../domain/contract";
import type { MemoryWords } from "./fact-actions";

const api = vi.hoisted(() => ({
  memoryApi: {
    imported: vi.fn<(cursor: string | null) => Promise<FactsPage>>(),
    accept: vi.fn<(id: string) => Promise<unknown>>(),
    forget: vi.fn<(id: string) => Promise<void>>(),
    turnDownImported: vi.fn<() => Promise<void>>(),
    list: vi.fn(),
  },
}));

vi.mock("../api/memory-api", () => api);
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { answerImported, importedResource, turnDownImported } = await import("./imported");

const fact = (id: string): MemoryFact => ({
  id,
  kind: "fact",
  statement: id,
  status: "candidate",
  pinned: false,
  source: { kind: "imported", title: null, thread_id: null, message_id: null },
  created_at: "2026-10-01T00:00:00Z",
});

const page = (...items: MemoryFact[]): FactsPage => ({
  items,
  next_cursor: null,
  counts: { active: 0, candidates: 0, imported: items.length },
});

const words = { t: (key: string) => key, common: (key: string) => key } as unknown as MemoryWords;

const shown = () => {
  const state = importedResource.getSnapshot();
  return state.status === "ready" ? state.data.items.map((f) => f.id) : null;
};

describe("the facts carried over from the earlier memory", () => {
  beforeEach(async () => {
    api.memoryApi.imported.mockResolvedValue(page(fact("a"), fact("b"), fact("c")));
    api.memoryApi.accept.mockReset().mockResolvedValue({});
    api.memoryApi.forget.mockReset().mockResolvedValue(undefined);
    api.memoryApi.turnDownImported.mockReset().mockResolvedValue(undefined);
    api.memoryApi.list.mockResolvedValue(page());
    await importedResource.refresh();
  });

  it("are answered one by one: remembered or turned down, each leaving the list", async () => {
    await answerImported(fact("a"), true, words);
    await answerImported(fact("b"), false, words);

    expect(api.memoryApi.accept.mock.calls).toEqual([["a"]]);
    expect(api.memoryApi.forget.mock.calls).toEqual([["b"]]);
    expect(shown()).toEqual(["c"]);
  });

  it("are turned down all at once", async () => {
    await turnDownImported(words);

    expect(api.memoryApi.turnDownImported).toHaveBeenCalledOnce();
    expect(shown()).toEqual([]);
  });
});
