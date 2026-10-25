import { describe, expect, it } from "vitest";

import { type AgentMessage, conversationOf, lastQuestion } from "./agent-history";

const row = (id: string, role: AgentMessage["role"], status: AgentMessage["status"] = null): AgentMessage => ({
  id,
  role,
  text: id,
  status,
  created_at: "2026-10-24T10:00:00Z",
  duration_ms: null,
  steps: [],
  sources: [],
  actions: [],
});

describe("a thread's history", () => {
  it("reads pages newest first into a conversation oldest first", () => {
    const pages = [
      { items: [row("a2", "assistant", "failed"), row("q2", "user")], next_cursor: "c" },
      { items: [row("a1", "assistant", "done"), row("q1", "user")], next_cursor: null },
    ];

    const conversation = conversationOf(pages);

    expect(conversation.map((m) => [m.id, m.role, m.status])).toEqual([
      ["q1", "user", "done"],
      ["a1", "assistant", "done"],
      ["q2", "user", "done"],
      ["a2", "assistant", "error"],
    ]);
    expect(lastQuestion(conversation)?.id).toBe("q2");
  });

  it("keeps an answer's steps and sources", () => {
    const answer = {
      ...row("a", "assistant", "done"),
      steps: [{ id: "step-1", activity: "tasks.search", detail: "trip", status: "done", duration_ms: 80 }],
      sources: [
        { id: "t", kind: "task", title: "Book travel", space: "Personal", locator: null, quote: "", highlight: [] },
      ],
    } satisfies AgentMessage;

    const [message] = conversationOf([{ items: [answer], next_cursor: null }]);

    expect(message.steps).toEqual([
      { id: "step-1", action: "tasks.search", detail: "trip", status: "done", durationMs: 80 },
    ]);
    expect(message.sources?.map((s) => [s.kind, s.space])).toEqual([["task", "Personal"]]);
  });
});
