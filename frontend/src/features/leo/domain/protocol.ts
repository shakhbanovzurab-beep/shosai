import type { LeoActionId } from "./actions";

// /api/leo streams newline-delimited JSON: one LeoEvent per line.
export type LeoEvent =
  | { type: "step_start"; id: string; action: LeoActionId; detail?: string }
  | { type: "step_end"; id: string; status: "done" | "error"; durationMs: number; result?: string }
  | { type: "text"; delta: string }
  | { type: "done"; durationMs: number }
  | { type: "error"; message: string };

export function encodeLeoEvent(event: LeoEvent) {
  return `${JSON.stringify(event)}\n`;
}
