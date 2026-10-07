import type { LeoActionId } from "./actions";

export type LeoMessageStatus = "streaming" | "done" | "stopped" | "error";

export interface LeoStep {
  id: string;
  action: LeoActionId;
  detail?: string;
  result?: string;
  status: "running" | "done" | "error" | "stopped";
  durationMs?: number;
}

// Only metadata is kept in history; the file contents are sent once, with the message they belong to.
export interface LeoAttachment {
  id: string;
  name: string;
  size: number;
  type: string;
}

export interface LeoMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: LeoMessageStatus;
  attachments?: LeoAttachment[];
  steps?: LeoStep[];
  durationMs?: number;
}
