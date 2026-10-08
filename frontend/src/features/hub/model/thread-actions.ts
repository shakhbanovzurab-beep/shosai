"use client";

import { toast } from "sonner";

import { hubApi } from "../api/hub-api";
import { errorCode } from "../api/hub-request";
import { DISMISS_DAYS, type Loaded } from "../domain/contract";
import type { ThreadSummary } from "../domain/contract-threads";
import { hubThreads, refreshAfterThreadChange, threadDetails } from "./resources";
import { type ActionWords, errorText } from "./words";

/*
 * Acting on a row: applied at once, confirmed with the server, put back as it was if the server says
 * no. "Done" and "Not the case" offer Undo in the toast. No confirmation dialogs: all of it is
 * reversible.
 */

type Rows = Loaded<ThreadSummary[]>;

/** Replaces (or drops, with null) one row everywhere it shows: the hub's list and the opened detail. */
function put(thread: ThreadSummary, next: ThreadSummary | null) {
  hubThreads.of(thread.hubId).update((rows: Rows) => {
    const known = rows.data.some((t) => t.id === thread.id);
    let data = rows.data.filter((t) => t.id !== thread.id);
    if (next) data = known ? rows.data.map((t) => (t.id === thread.id ? next : t)) : [...rows.data, next];
    return { ...rows, data };
  });
  if (next) threadDetails.loaded(thread.id)?.update((detail) => ({ ...detail, ...next }));
}

/** Shows `after` at once, keeps what the server returns, and puts `before` back if it refuses. Null: no row. */
async function apply(
  words: ActionWords,
  thread: ThreadSummary,
  [before, after]: [ThreadSummary | null, ThreadSummary | null],
  request: () => Promise<ThreadSummary>,
) {
  put(thread, after);
  try {
    const saved = await request();
    put(thread, after ? saved : null);
    refreshAfterThreadChange(thread.hubId, thread.id);
    return true;
  } catch (error) {
    put(thread, before);
    toast.error(words.hub("saveFailed"), { description: errorText(words.api, errorCode(error)) });
    return false;
  }
}

/** "Done": the row leaves the list at once; Undo brings it back. */
export async function markDone(words: ActionWords, thread: ThreadSummary) {
  if (!(await apply(words, thread, [thread, null], () => hubApi.done(thread.id)))) return;
  toast.success(words.blocks("unresolved.doneToast"), {
    description: thread.subject,
    action: {
      label: words.common("actions.undo"),
      onClick: () => void apply(words, thread, [null, thread], () => hubApi.undoDone(thread.id)),
    },
  });
}

/** "Abandoned": closed without being done, from the detail panel. */
export async function markAbandoned(words: ActionWords, thread: ThreadSummary) {
  if (!(await apply(words, thread, [thread, null], () => hubApi.abandon(thread.id)))) return;
  threadDetails.loaded(thread.id)?.update((detail) => ({ ...detail, stage: "abandoned", gap: null }));
  toast.success(words.blocks("unresolved.abandonToast"), { description: thread.subject });
}

/** "Not the case": the gap is off for 90 days, here, in the hub's counter and in the assistant's signals. */
export async function dismissGap(words: ActionWords, thread: ThreadSummary) {
  const gap = thread.gap;
  if (!gap) return;
  const now = new Date();
  const dismissed: ThreadSummary = {
    ...thread,
    gap: null,
    refutation: {
      by: "human",
      at: now.toISOString(),
      evidence: "",
      until: new Date(now.getTime() + DISMISS_DAYS * 86_400_000).toISOString(),
      returned: false,
    },
  };
  if (!(await apply(words, thread, [thread, dismissed], () => hubApi.dismiss(thread.id, gap.kind)))) return;
  toast.success(words.blocks("unresolved.dismissToast", { days: DISMISS_DAYS }), {
    description: thread.subject,
    action: {
      label: words.common("actions.undo"),
      onClick: () => void apply(words, thread, [dismissed, thread], () => hubApi.undoDismiss(thread.id)),
    },
  });
}

/** "Assign": nobody owning it is a valid state, so this is offered, never demanded. */
export async function assignOwner(words: ActionWords, thread: ThreadSummary, owner: string) {
  const name = owner.trim();
  if (!name) return false;
  const saved = await apply(words, thread, [thread, { ...thread, owner: name }], () => hubApi.assign(thread.id, name));
  if (saved) toast.success(words.blocks("unresolved.assignedToast", { owner: name }), { description: thread.subject });
  return saved;
}
