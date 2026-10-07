import type { LanguageCode } from "@/lib/language";

import { isLeoActionId } from "../domain/actions";
import type { LeoContext } from "../domain/context";
import type { LeoEvent } from "../domain/protocol";
import type { LeoMessage, LeoMessageStatus } from "../domain/types";

/* Talking to /api/leo: sending the history and files, reading the newline-delimited event stream. */

function parseEvent(line: string): LeoEvent | null {
  try {
    const event = JSON.parse(line) as LeoEvent;
    if (event.type === "step_start" && !isLeoActionId(event.action)) return null;
    return event;
  } catch {
    return null;
  }
}

interface StreamReplyOptions {
  page: string;
  locale: LanguageCode;
  context: LeoContext;
  history: LeoMessage[];
  files: File[];
  signal: AbortSignal;
  onEvent: (event: LeoEvent) => void;
}

/** The context as the server reads it: a workspace or a hub by id, or Personal. */
function payloadContext(context: LeoContext) {
  if (context.kind === "workspace") return { kind: "workspace", workspace_id: context.id };
  if (context.kind === "hub") return { kind: "hub", hub_id: context.id };
  return { kind: "personal" };
}
export async function streamReply({
  page,
  locale,
  context,
  history,
  files,
  signal,
  onEvent,
}: StreamReplyOptions): Promise<LeoMessageStatus | null> {
  try {
    const body = new FormData();
    body.append(
      "payload",
      JSON.stringify({
        page,
        locale,
        context: payloadContext(context),
        messages: history
          .filter((m) => m.status !== "error" && (m.content.trim() || m.attachments?.length))
          .map(({ role, content, attachments }) => ({
            role,
            content,
            attachments: attachments?.map(({ name, size, type }) => ({ name, size, type })),
          })),
      }),
    );
    for (const file of files) body.append("files", file);

    const response = await fetch("/api/leo", { method: "POST", body, signal });
    if (!response.ok || !response.body) throw new Error(`Request failed with status ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (let result = await reader.read(); !result.done; result = await reader.read()) {
      buffer += decoder.decode(result.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const event = line.trim() ? parseEvent(line) : null;
        if (event) onEvent(event);
      }
    }
    // The stream finished normally; the final status came with the "done" or "error" event.
    return null;
  } catch {
    return signal.aborted ? "stopped" : "error";
  }
}
