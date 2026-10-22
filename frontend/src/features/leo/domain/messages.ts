import type { LeoEvent } from "./protocol";
import type { LeoMessage, LeoMessageStatus, LeoStep } from "./types";

/* How Leo's reply changes as the /api/leo event stream comes in. */

export function finishMessage(message: LeoMessage, status: LeoMessageStatus): LeoMessage {
  return {
    ...message,
    status,
    steps: message.steps?.map((step) => (step.status === "running" ? { ...step, status: "stopped" } : step)),
  };
}

export function applyEvent(message: LeoMessage, event: LeoEvent): LeoMessage {
  const steps = message.steps ?? [];
  switch (event.type) {
    case "step_start":
      return {
        ...message,
        steps: [...steps, { id: event.id, action: event.action, detail: event.detail, status: "running" }],
      };
    case "step_end":
      return {
        ...message,
        steps: steps.map(
          (step): LeoStep =>
            step.id === event.id
              ? { ...step, status: event.status, durationMs: event.durationMs, result: event.result }
              : step,
        ),
      };
    case "text":
      return { ...message, content: message.content + event.delta };
    case "sources":
      return { ...message, sources: event.sources };
    case "proposal":
      return { ...message, proposals: [...(message.proposals ?? []), event.proposal] };
    case "artifact":
      return { ...message, artifacts: [...(message.artifacts ?? []), event.artifact] };
    case "done":
      return { ...finishMessage(message, "done"), durationMs: event.durationMs };
    case "error":
      return finishMessage(message, "error");
  }
}
