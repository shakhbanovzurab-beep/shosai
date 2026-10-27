import { describe, expect, it } from "vitest";

import type { LiveTurn } from "../domain/live-turns";
import type { LeoMessage } from "../domain/types";
import { addTurn, dropTurns, withMeasured } from "./agent-turns";

const answer = (id: string, durationMs?: number): LeoMessage => ({
  id,
  role: "assistant",
  content: "Done.",
  status: "done",
  ...(durationMs === undefined ? {} : { durationMs }),
});

const ended = (replyId: string, durationMs: number): LiveTurn => ({
  key: `k-${replyId}`,
  kind: "new",
  threadId: "t",
  question: { id: `q-${replyId}`, role: "user", content: "Hi?", status: "done" },
  reply: answer(replyId, durationMs),
  runId: "r",
  seq: 9,
  startedAt: 0,
});

describe("the time a person saw an answer take", () => {
  it("stays the same when the history comes back with the server's shorter time", () => {
    const live = [ended("a1", 10_200)];
    const history = [answer("a0", 3_000), answer("a1", 7_900)];

    expect(withMeasured(history, live).map((m) => m.durationMs)).toEqual([3_000, 10_200]);
  });

  it("stays after the live turn is dropped as recorded", () => {
    addTurn("personal", ended("a2", 6_400));
    dropTurns("personal", () => true);

    expect(withMeasured([answer("a2", 4_100)], []).map((m) => m.durationMs)).toEqual([6_400]);
  });

  it("leaves answers it never saw live untouched", () => {
    const history = [answer("a9", 5_000)];

    expect(withMeasured(history, [])).toBe(history);
  });
});
