"use client";

import { toast } from "sonner";

import { hubApi } from "../api/hub-api";
import { errorCode } from "../api/hub-request";
import type { HubRef, MeetingHub } from "../domain/contract";
import { meetingHubs, refreshAfterFiling } from "./resources";
import { type ActionWords, errorText } from "./words";

/*
 * A person files a meeting in a hub, or takes it out. Their word outranks the machine's and is
 * remembered for the meeting's calendar series, which the toast says. Undo puts back what was there.
 */

async function change(words: ActionWords, meetingId: string, hubId: string, request: () => Promise<MeetingHub>) {
  try {
    const next = await request();
    meetingHubs.of(meetingId).update(() => next);
    refreshAfterFiling(hubId);
    return true;
  } catch (error) {
    toast.error(words.hub("saveFailed"), { description: errorText(words.api, errorCode(error)) });
    return false;
  }
}

export async function fileMeeting(words: ActionWords, meetingId: string, hub: HubRef) {
  if (!(await change(words, meetingId, hub.id, () => hubApi.fileMeeting(hub.id, meetingId)))) return;
  toast.success(words.meetings("chip.filedToast"), {
    description: hub.name,
    action: {
      label: words.common("actions.undo"),
      onClick: () => void change(words, meetingId, hub.id, () => hubApi.unfileMeeting(hub.id, meetingId)),
    },
  });
}

export async function unfileMeeting(words: ActionWords, meetingId: string, before: MeetingHub) {
  const hub = before.hub;
  if (!hub) return;
  if (!(await change(words, meetingId, hub.id, () => hubApi.unfileMeeting(hub.id, meetingId)))) return;
  toast.success(words.meetings("chip.removedToast", { hub: hub.name }), {
    action: {
      label: words.common("actions.undo"),
      onClick: () => void change(words, meetingId, hub.id, () => hubApi.fileMeeting(hub.id, meetingId)),
    },
  });
}
