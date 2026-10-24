import { describe, expect, it } from "vitest";

import { isRecorded, type LiveTurn, mergedConversation } from "./live-turns";
import type { LeoMessage } from "./types";

const said = (id: string, role: LeoMessage["role"], content = id): LeoMessage => ({
  id,
  role,
  content,
  status: "done",
});

const turn = (kind: LiveTurn["kind"], question: LeoMessage, replyId: string): LiveTurn => ({
  key: `k-${replyId}`,
  kind,
  threadId: "t",
  question,
  reply: { id: replyId, role: "assistant", content: "…", status: "streaming", steps: [] },
  runId: null,
  seq: 1,
  startedAt: 0,
});

const history = [said("q1", "user"), said("a1", "assistant"), said("q2", "user"), said("a2", "assistant")];

describe("the conversation a person sees", () => {
  it("adds a new question and its streaming answer after the history", () => {
    const merged = mergedConversation(history, [turn("new", said("q3", "user"), "a3")]);

    expect(merged.map((m) => m.id)).toEqual(["q1", "a1", "q2", "a2", "q3", "a3"]);
  });

  it("puts a regenerated answer in place of the old one, an edit with its new text", () => {
    const again = mergedConversation(history, [turn("regenerate", said("q2", "user"), "a2b")]);
    const edited = mergedConversation(history, [turn("edit", said("q2", "user", "Better?"), "a2c")]);

    expect(again.map((m) => m.id)).toEqual(["q1", "a1", "q2", "a2b"]);
    expect(edited.map((m) => [m.id, m.content])).toEqual([
      ["q1", "q1"],
      ["a1", "a1"],
      ["q2", "Better?"],
      ["a2c", "…"],
    ]);
  });

  it("lets the history take over once it holds the answer", () => {
    const live = turn("new", said("q3", "user"), "a3");
    const ended = { ...live, reply: { ...live.reply, status: "done" as const } };
    const recorded = [...history, said("q3", "user"), said("a3", "assistant")];

    expect(mergedConversation(recorded, [live]).map((m) => m.id)).toEqual(["q1", "a1", "q2", "a2", "q3", "a3"]);
    expect([isRecorded(live, recorded), isRecorded(ended, recorded), isRecorded(ended, history)]).toEqual([
      false,
      true,
      false,
    ]);
  });
});
