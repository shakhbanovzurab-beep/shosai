import type { LeoActionId } from "./actions";
import type { LeoMessage, LeoStep } from "./types";

// Short steps are noise; only steps that took noticeable time show their duration.
export const MIN_VISIBLE_DURATION_MS = 1000;

/** The one line shown above a reply's steps, as data: what Leo is doing now, or how the reply ended. */
export type StepsSummary =
  | { kind: "running"; action: LeoActionId }
  | { kind: "starting" }
  | { kind: "stopped"; ms: number }
  | { kind: "error" }
  | { kind: "done"; ms: number };

export function getStepsSummary(message: LeoMessage, steps: LeoStep[]): StepsSummary {
  const ms = message.durationMs ?? steps.reduce((sum, step) => sum + (step.durationMs ?? 0), 0);
  switch (message.status) {
    case "streaming": {
      const current = steps.findLast((step) => step.status === "running");
      return current ? { kind: "running", action: current.action } : { kind: "starting" };
    }
    case "stopped":
      return { kind: "stopped", ms };
    case "error":
      return { kind: "error" };
    default:
      return { kind: "done", ms };
  }
}
