import { finishMessage } from "./messages";
import type { LeoSource } from "./sources";
import type { SseEvent } from "./sse";
import type { LeoMessage, LeoStep } from "./types";

/*
 * События хода Leo из `/v1/agent` (SSE v2, docs/leo-api.md): у каждого номер прогона, который поток возобновляет
 * после `Last-Event-ID`. Неизвестный вид события пропускается: сервер может прислать новый раньше кабинета.
 */

export type RunEvent =
  | { kind: "run.started"; data: { run_id: string; thread_id: string; message_id: string; reply_id: string } }
  | { kind: "step.started"; data: { id: string; activity: string; detail?: string | null } }
  | { kind: "step.completed"; data: { id: string; duration_ms: number } }
  | { kind: "step.failed"; data: { id: string; duration_ms: number; code: string } }
  | { kind: "text.delta"; data: { text: string } }
  | { kind: "sources"; data: { sources: LeoSource[] } }
  | { kind: "client.action"; data: { navigate?: { to: string } } }
  | { kind: "run.completed"; data: { message_id: string; outcome: "answered" | "stopped"; truncated: boolean } }
  | { kind: "run.failed"; data: { code: string } };

export type NumberedEvent = RunEvent & { seq: number };

const KINDS = new Set<string>([
  "run.started",
  "step.started",
  "step.completed",
  "step.failed",
  "text.delta",
  "sources",
  "client.action",
  "run.completed",
  "run.failed",
]);

/** Событие хода из события SSE, или null для неизвестного вида и испорченных данных. */
export function runEventOf(sse: SseEvent): NumberedEvent | null {
  if (!KINDS.has(sse.event)) return null;
  const seq = Number(sse.id);
  if (!Number.isInteger(seq)) return null;
  try {
    const data: unknown = JSON.parse(sse.data);
    if (typeof data !== "object" || data === null) return null;
    return { kind: sse.event, data, seq } as NumberedEvent;
  } catch {
    return null;
  }
}

/** Конец хода: последний для прогона, после него поток молчит. */
export const isTerminal = (event: RunEvent) => event.kind === "run.completed" || event.kind === "run.failed";

function closeStep(steps: LeoStep[], id: string, change: Partial<LeoStep>): LeoStep[] {
  return steps.map((step) => (step.id === id ? { ...step, ...change } : step));
}

/** Ответ Leo после события его хода. */
export function applyRunEvent(message: LeoMessage, event: RunEvent): LeoMessage {
  const steps = message.steps ?? [];
  switch (event.kind) {
    case "step.started": {
      const { id, activity, detail } = event.data;
      const step: LeoStep = { id, action: activity, detail: detail ?? undefined, status: "running" };
      return { ...message, steps: [...steps, step] };
    }
    case "step.completed":
      return {
        ...message,
        steps: closeStep(steps, event.data.id, { status: "done", durationMs: event.data.duration_ms }),
      };
    case "step.failed":
      return {
        ...message,
        steps: closeStep(steps, event.data.id, { status: "error", durationMs: event.data.duration_ms }),
      };
    case "text.delta":
      return { ...message, content: message.content + event.data.text };
    case "sources":
      return { ...message, sources: event.data.sources };
    case "run.completed":
      return finishMessage(message, event.data.outcome === "stopped" ? "stopped" : "done");
    case "run.failed":
      return { ...finishMessage(message, "error"), failure: { code: event.data.code } };
    default:
      return message;
  }
}
