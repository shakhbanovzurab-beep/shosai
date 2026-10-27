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
  artifacts: [],
  actions: [],
  feedback: null,
  attachments: [],
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

  it("shows a card on its answer once, hiding the server's note about it", () => {
    const card = {
      id: "a1",
      tool: "tasks.create",
      title: "Create the task",
      space: "Personal",
      origin: { kind: "thread", app: null },
      reversibility: "reversible",
      warning: false,
      taint: null,
      suspicious: false,
      preview: { kind: "fields", fields: [], body: null },
      status: "succeeded",
      outcome: null,
      nonce: "n",
      created_at: "2026-10-24T10:00:00Z",
      expires_at: "2026-10-24T11:00:00Z",
      resolved_at: "2026-10-24T10:01:00Z",
    } satisfies AgentMessage["actions"][number];
    const artifact = { kind: "chat_digest", ref: "d", alt: "Digest", workspace_id: "w", chat_id: "c" } as const;
    const answer = { ...row("a", "assistant", "done"), actions: [card], artifacts: [artifact] };
    const note = { ...row("n", "server"), text: "", actions: [card] };
    const lonely = { ...row("m", "server"), text: "", actions: [{ ...card, id: "a2" }] };

    const conversation = conversationOf([{ items: [lonely, answer, note, row("q", "user")], next_cursor: null }]);

    expect(conversation.map((m) => [m.id, m.role, m.proposals?.map((p) => p.id)])).toEqual([
      ["q", "user", undefined],
      ["a", "assistant", ["a1"]],
      ["m", "assistant", ["a2"]],
    ]);
    expect(conversation[1].artifacts).toEqual([artifact]);
    expect([conversation[0].feedback, conversation[1].feedback]).toEqual([undefined, null]);
  });

  it("shows a question's files and leaves a question without them bare", () => {
    const file = { id: "u1", name: "plan.txt", size: 62, type: "text/plain" };
    const pages = [{ items: [row("q2", "user"), { ...row("q1", "user"), attachments: [file] }], next_cursor: null }];

    const [first, second] = conversationOf(pages);

    expect([first.attachments, second.attachments]).toEqual([[file], undefined]);
  });
});
