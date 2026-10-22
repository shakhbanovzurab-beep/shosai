import { describe, expect, it } from "vitest";

import type { ChatDigest, DigestItem, DigestPromise } from "./digest-contract";
import { coverageNotes, coveredFrom, digestContent, freePromises, itemTask } from "./digest-rules";

const item = (id: string, extra: Partial<DigestItem> = {}): DigestItem => ({
  id,
  text: id,
  message: { id: `m-${id}`, author_name: "Maya", sent_at: "2026-10-20T10:00:00Z", quote: "…", url: null },
  proposal_id: null,
  task_id: null,
  ...extra,
});

const promise = (id: string, extra: Partial<DigestItem> = {}): DigestPromise => ({
  ...item(id, extra),
  who: { user_id: null, name: "Sam" },
  due_on: null,
  when_text: null,
});

const digest = (extra: Partial<ChatDigest> = {}): ChatDigest => ({
  id: "dg",
  chat: { id: "c", workspace_id: "w", messenger: "telegram", title: "Release", binding: { kind: "workspace" } },
  period: { from: "2026-10-15T00:00:00Z", to: "2026-10-22T00:00:00Z" },
  created_at: "2026-10-22T00:00:00Z",
  coverage: { history_from: "2026-10-01T00:00:00Z", messages_read: 412, truncated: false },
  decisions: [],
  questions: [],
  promises: [],
  ...extra,
});

describe("a digest item and its task", () => {
  it("is created, waiting, being made or free", () => {
    expect(itemTask(item("a", { task_id: "t1", proposal_id: "p1" }), new Set())).toEqual({
      kind: "created",
      taskId: "t1",
    });
    expect(itemTask(item("a", { proposal_id: "p1" }), new Set())).toEqual({ kind: "waiting", proposalId: "p1" });
    expect(itemTask(item("a"), new Set(["a"]))).toEqual({ kind: "making" });
    expect(itemTask(item("a"), new Set())).toEqual({ kind: "free" });
  });

  it("offers only free promises, at most one card's worth", () => {
    const promises = [promise("p1", { task_id: "t" }), promise("p2", { proposal_id: "x" })];
    for (let n = 3; n <= 25; n++) promises.push(promise(`p${n}`));
    const free = freePromises(digest({ promises }));
    expect(free).toHaveLength(20);
    expect(free[0].id).toBe("p3");
  });
});

describe("a digest's coverage", () => {
  it("notes a period that starts before Shosai had the chat's messages, and a cut one", () => {
    const late = digest({ coverage: { history_from: "2026-10-18T00:00:00Z", messages_read: 40, truncated: true } });
    expect(coverageNotes(late)).toEqual([{ kind: "history", from: "2026-10-18T00:00:00Z" }, { kind: "truncated" }]);
    expect(coveredFrom(late)).toBe("2026-10-18T00:00:00Z");
    expect(coverageNotes(digest())).toEqual([]);
    expect(coveredFrom(digest())).toBe("2026-10-15T00:00:00Z");
  });

  it("tells no messages from nothing to note", () => {
    expect(digestContent(digest({ coverage: { ...digest().coverage, messages_read: 0 } }))).toBe("no_messages");
    expect(digestContent(digest())).toBe("nothing_found");
    expect(digestContent(digest({ decisions: [item("d1")] }))).toBe("items");
  });
});
