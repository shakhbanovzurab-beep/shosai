import { describe, expect, it } from "vitest";

import { applyRunEvent, type RunEvent, runEventOf } from "./run-events";
import { SseParser } from "./sse";
import type { LeoMessage } from "./types";

const reply: LeoMessage = { id: "r", role: "assistant", content: "", status: "streaming", steps: [] };

describe("the stream of a turn", () => {
  it("reads events split anywhere across chunks, skipping heartbeats", () => {
    const parser = new SseParser();
    const wire =
      ': ping\n\nevent: text.delta\nid: 2\ndata: {"text":"Hel"}\n\nevent: text.delta\r\nid: 3\r\ndata: {"text":"lo"}\r\n\r\n';
    const events = [...wire].flatMap((char) => parser.push(char));

    expect(events).toEqual([
      { event: "text.delta", id: "2", data: '{"text":"Hel"}' },
      { event: "text.delta", id: "3", data: '{"text":"lo"}' },
    ]);
  });

  it("drops unknown kinds and broken data, numbers the rest", () => {
    expect(runEventOf({ event: "future.kind", id: "4", data: "{}" })).toBeNull();
    expect(runEventOf({ event: "text.delta", id: "4", data: "{oops" })).toBeNull();
    expect(runEventOf({ event: "text.delta", id: "x", data: '{"text":"a"}' })).toBeNull();
    expect(runEventOf({ event: "text.delta", id: "4", data: '{"text":"a"}' })).toEqual({
      kind: "text.delta",
      data: { text: "a" },
      seq: 4,
    });
  });

  it("builds a reply from its steps, text, sources and end", () => {
    const events: RunEvent[] = [
      { kind: "step.started", data: { id: "step-1", activity: "notes.search", detail: "budget" } },
      { kind: "step.failed", data: { id: "step-1", duration_ms: 40, code: "timeout" } },
      { kind: "text.delta", data: { text: "Cut [1]." } },
      {
        kind: "sources",
        data: {
          sources: [
            { id: "m", kind: "meeting", title: "T", space: "Personal", locator: null, quote: "", highlight: [] },
          ],
        },
      },
      { kind: "run.failed", data: { code: "turn_deadline" } },
    ];

    const built = events.reduce((message, event) => applyRunEvent(message, event), reply);

    expect(built.steps).toEqual([
      { id: "step-1", action: "notes.search", detail: "budget", status: "error", durationMs: 40 },
    ]);
    expect(built.content).toBe("Cut [1].");
    expect(built.sources?.[0].space).toBe("Personal");
    expect([built.status, built.failure]).toEqual(["error", { code: "turn_deadline" }]);
  });

  it("closes a stopped reply with its running steps stopped", () => {
    const running = applyRunEvent(reply, { kind: "step.started", data: { id: "s", activity: "tasks.search" } });
    const stopped = applyRunEvent(running, {
      kind: "run.completed",
      data: { message_id: "r", outcome: "stopped", truncated: false },
    });

    expect([stopped.status, stopped.steps?.[0].status]).toEqual(["stopped", "stopped"]);
  });
});
