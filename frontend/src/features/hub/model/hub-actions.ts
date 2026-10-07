"use client";

import { toast } from "sonner";

import { hubApi } from "../api/hub-api";
import { errorCode } from "../api/hub-request";
import type { Hub } from "../domain/contract";
import type { HubErrorCode } from "../domain/errors";
import { brief, dropHub, hubLists, preps, receiveHub } from "./resources";
import { type ActionWords, errorText } from "./words";

/*
 * Changing a hub. Its name and charter only ever come from a person: nothing here drafts or fills
 * them in. Archiving is the one step the screens ask about first (with what's still open); restoring
 * and everything else just happen.
 */

export type Outcome = { ok: true; hub: Hub } | { ok: false; code: HubErrorCode };

async function attempt(request: () => Promise<Hub>): Promise<Outcome> {
  try {
    const hub = await request();
    receiveHub(hub);
    return { ok: true, hub };
  } catch (error) {
    return { ok: false, code: errorCode(error) };
  }
}

const failed = (words: ActionWords, code: HubErrorCode) =>
  toast.error(words.hub("saveFailed"), { description: errorText(words.api, code) });

/** Creates a hub from the name a person typed; the form shows a refusal under the field. */
export async function createHub(words: ActionWords, name: string) {
  const outcome = await attempt(() => hubApi.create(name));
  if (outcome.ok) toast.success(words.hub("form.created", { name: outcome.hub.name }));
  return outcome;
}

export async function renameHub(words: ActionWords, hub: Hub, name: string) {
  const outcome = await attempt(() => hubApi.rename(hub.id, name));
  if (outcome.ok) {
    toast.success(words.hub("form.renamed"));
    void brief.refresh();
  }
  return outcome;
}

export async function saveCharter(words: ActionWords, hub: Hub, purpose: string, success: string) {
  const outcome = await attempt(() => hubApi.charter(hub.id, purpose.trim() || null, success.trim() || null));
  if (outcome.ok) toast.success(words.hub("page.charterSaved"));
  else failed(words, outcome.code);
  return outcome.ok;
}

export async function chooseBoard(words: ActionWords, hub: Hub, boardId: string | null) {
  const outcome = await attempt(() => hubApi.board(hub.id, boardId));
  if (outcome.ok) toast.success(words.hub("dialogs.boardSaved"), { description: outcome.hub.boardName ?? undefined });
  else failed(words, outcome.code);
  return outcome.ok;
}

export async function restoreHub(words: ActionWords, hub: Hub) {
  const outcome = await attempt(() => hubApi.archived(hub.id, false));
  if (outcome.ok) toast.success(words.hub("dialogs.restoredToast", { name: hub.name }));
  else failed(words, outcome.code);
  void brief.refresh();
  void preps.refresh();
  return outcome.ok;
}

/** After the archive dialog: out of the active list; Undo brings it back without a question. */
export async function archiveHub(words: ActionWords, hub: Hub) {
  const outcome = await attempt(() => hubApi.archived(hub.id, true));
  if (!outcome.ok) return failed(words, outcome.code);
  void brief.refresh();
  void preps.refresh();
  toast.success(words.hub("dialogs.archivedToast", { name: hub.name }), {
    action: { label: words.common("actions.undo"), onClick: () => void restoreHub(words, hub) },
  });
}

/** Deletes the hub and its addressing; meetings, tasks and documents stay where they are. */
export async function deleteHub(words: ActionWords, hub: Hub) {
  try {
    await hubApi.remove(hub.id);
    dropHub(hub.id);
    void brief.refresh();
    void preps.refresh();
    toast.success(words.hub("dialogs.deletedToast", { name: hub.name }));
    return true;
  } catch (error) {
    failed(words, errorCode(error));
    void hubLists.active.refresh();
    return false;
  }
}
