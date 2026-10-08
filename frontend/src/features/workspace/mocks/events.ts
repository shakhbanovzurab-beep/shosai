import type { WorkspaceData, WorkspaceEventAction } from "./types";

/* The platform's event log and the few facts about a workspace the platform's team relies on. */

type Change = { target?: string | null; value?: string | null };

/** Adds an event, newest first; `actor` is the member who did it, or null for the platform's team. */
export function logEvent(
  data: WorkspaceData,
  action: WorkspaceEventAction,
  actor: { name: string } | null,
  { target = null, value = null }: Change = {},
) {
  data.control.events.unshift({
    id: `ev-${crypto.randomUUID().slice(0, 8)}`,
    at: new Date().toISOString(),
    action,
    actor: actor?.name ?? null,
    target,
    value,
  });
}

/** Members and pending invitations both hold a seat. */
export const seatsUsed = (data: WorkspaceData) => data.members.length + data.invitations.length;

export const isSuspended = (data: WorkspaceData) => data.control.suspended !== null;
