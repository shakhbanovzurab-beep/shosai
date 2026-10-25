import { describe, expect, it } from "vitest";

import { appliedEpilogue, startedEpilogue, withEpilogues } from "./epilogues";
import type { LeoProposal } from "./proposals";
import { applyRunEvent, type NumberedEvent, runEventOf } from "./run-events";
import type { LeoMessage } from "./types";

const card = (status: LeoProposal["status"]): LeoProposal => ({
  id: "a1",
  tool: "tasks.create",
  title: "Create the task “Call Jonas”",
  space: "Personal",
  origin: { kind: "thread", app: null },
  reversibility: "reversible",
  warning: false,
  taint: "mail",
  preview: { kind: "fields", fields: [{ label: "Title", value: "Call Jonas" }], body: null },
  status,
  outcome: null,
  nonce: "n",
  created_at: "2026-10-25T10:00:00Z",
  expires_at: "2026-10-25T11:00:00Z",
  resolved_at: status === "proposed" ? null : "2026-10-25T10:01:00Z",
});

let seq = 0;
const at = <E extends NumberedEvent>(event: Omit<E, "seq">) => ({ ...event, seq: ++seq }) as NumberedEvent;

// Журнал прогона с карточкой: слова, карточка, пауза; после одобрения — итог и эпилог.
const log: NumberedEvent[] = [
  at({ kind: "run.started", data: { run_id: "r", thread_id: "t", message_id: "q", reply_id: "a" } }),
  at({ kind: "text.delta", data: { text: "I prepared the task. " } }),
  at({ kind: "action.proposed", data: { action: card("proposed") } }),
  at({ kind: "run.paused", data: { action_id: "a1" } }),
  at({ kind: "action.updated", data: { action: card("succeeded"), invalidates: ["tasks"] } }),
  at({ kind: "step.started", data: { id: "s2", activity: "write_answer" } }),
  at({ kind: "text.delta", data: { text: "Done." } }),
  at({ kind: "run.completed", data: { message_id: "a", outcome: "answered", truncated: false } }),
];

describe("a run with a card", () => {
  it("reads the new kinds from the wire", () => {
    const sse = { event: "run.paused", id: "4", data: '{"action_id":"a1"}' };
    expect(runEventOf(sse)).toEqual({ kind: "run.paused", data: { action_id: "a1" }, seq: 4 });
  });

  it("pauses the answer on its card, then goes on after the decision", () => {
    const blank: LeoMessage = { id: "a", role: "assistant", content: "", status: "streaming", steps: [] };
    const paused = log.slice(1, 4).reduce(applyRunEvent, blank);
    expect([paused.status, paused.proposals?.map((p) => p.status)]).toEqual(["done", ["proposed"]]);

    const decided = applyRunEvent(paused, log[4]);
    expect([decided.status, decided.proposals?.map((p) => p.status)]).toEqual(["streaming", ["succeeded"]]);
  });

  it("rebuilds the whole answer from the first event and stands in for its history row", () => {
    const epilogue = log.reduce(appliedEpilogue, startedEpilogue("r"));
    expect(epilogue.threadId).toBe("t");
    expect(epilogue.reply?.content).toBe("I prepared the task. Done.");
    expect(epilogue.reply?.proposals).toEqual([card("succeeded")]);
    expect(epilogue.reply?.status).toBe("done");

    const history: LeoMessage[] = [
      { id: "q", role: "user", content: "Make a task", status: "done" },
      { id: "a", role: "assistant", content: "I prepared the task. ", status: "done", proposals: [card("proposed")] },
    ];
    const shown = withEpilogues(history, [epilogue]);
    expect(shown.map((m) => m.content)).toEqual(["Make a task", "I prepared the task. Done."]);
  });

  it("keeps the history as it is until the run names its answer", () => {
    const history: LeoMessage[] = [{ id: "a", role: "assistant", content: "So far", status: "done" }];
    expect(withEpilogues(history, [startedEpilogue("r")])).toBe(history);
  });

  it("adds a handed-over artifact to the answer", () => {
    const artifact = { kind: "chat_digest", ref: "d", alt: "Digest", workspace_id: "w", chat_id: "c" } as const;
    const blank: LeoMessage = { id: "a", role: "assistant", content: "", status: "streaming" };
    expect(applyRunEvent(blank, { kind: "artifact", data: artifact }).artifacts).toEqual([artifact]);
  });
});
