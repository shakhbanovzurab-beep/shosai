import type { LeoActionId } from "./actions";
import type { LeoProposal } from "./proposals";
import type { LeoSource } from "./sources";

// /api/leo streams newline-delimited JSON: one LeoEvent per line.
export type LeoEvent =
  | { type: "step_start"; id: string; action: LeoActionId; detail?: string }
  | { type: "step_end"; id: string; status: "done" | "error"; durationMs: number; result?: string }
  | { type: "text"; delta: string }
  // Источники ответа и предложенные действия — предложение к SSE v2 (ADR 0032), пока только в моках.
  | { type: "sources"; sources: LeoSource[] }
  | { type: "proposal"; proposal: LeoProposal }
  | { type: "done"; durationMs: number }
  | { type: "error"; message: string };

export function encodeLeoEvent(event: LeoEvent) {
  return `${JSON.stringify(event)}\n`;
}
