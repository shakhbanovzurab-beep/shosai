"use client";

import type { ReactNode } from "react";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import type { MeetingShareRequest, ShareRecordingRequest, TeamMeetingDetail } from "../domain/content-contract";
import { refreshShared, resourcesOf } from "./resources";
import { words } from "./words";

/*
 * Sharing is the one change people most need to take back quickly, so every change of who sees a
 * meeting comes with Undo in its toast. `phrase` is the confirmation, worded by the caller.
 */

const undo = () => words((_, common) => common("actions.undo"));

function received(ws: string, meeting: TeamMeetingDetail) {
  resourcesOf(ws)
    .meeting(meeting.id)
    .update(() => meeting);
  refreshShared(ws);
}

/** Shares one of the account's recordings into a workspace (moving it there if it was shared elsewhere). */
export async function shareRecording(
  ws: string,
  request: ShareRecordingRequest,
  phrase: ReactNode,
  previousWs?: string,
) {
  try {
    received(ws, await resourcesOf(ws).api.shareRecording(request));
    if (previousWs && previousWs !== ws) refreshShared(previousWs);
    toast.success(phrase, {
      action: { label: undo(), onClick: () => void unshareMeeting(ws, request.recording_id, null) },
    });
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.meetingShareFailed")),
      { description: errorMessage(error) },
    );
    return false;
  }
}

/** Changes who sees a shared meeting, its transcript or its project; `undo` restores the previous values. */
export async function updateMeeting(
  ws: string,
  id: string,
  change: MeetingShareRequest,
  phrase: ReactNode,
  previous?: MeetingShareRequest,
) {
  try {
    received(ws, await resourcesOf(ws).api.updateMeeting(id, change));
    const undone = words((t) => t("toasts.changeUndone"));
    toast.success(
      phrase,
      previous ? { action: { label: undo(), onClick: () => void updateMeeting(ws, id, previous, undone) } } : undefined,
    );
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.meetingChangeFailed")),
      { description: errorMessage(error) },
    );
    return false;
  }
}

/**
 * Takes a meeting out of the workspace; it stays in its owner's Notes. With `restore`, Undo shares it
 * back as it was.
 */
export async function unshareMeeting(ws: string, id: string, restore: ShareRecordingRequest | null, mine = true) {
  const where = words((t) => t(mine ? "toasts.stillInYourNotes" : "toasts.stillInOwnerNotes"));
  try {
    await resourcesOf(ws).api.unshareMeeting(id);
    resourcesOf(ws)
      .meeting(id)
      .update(() => null);
    refreshShared(ws);
    const again = words((t) => t("toasts.sharedAgain"));
    toast.success(
      words((t) => t("toasts.noLongerShared")),
      restore
        ? { description: where, action: { label: undo(), onClick: () => void shareRecording(ws, restore, again) } }
        : { description: where },
    );
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.unshareMeetingFailed")),
      { description: errorMessage(error) },
    );
    return false;
  }
}
