"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { livekitApi } from "../api/livekit-api";
import {
  LIVEKIT_POLL_MS,
  type LiveKitOverview,
  type LiveKitParticipant,
  type LiveKitRoom,
  type LiveKitRoomDetail,
} from "../domain/contract";
import { withLiveRefresh } from "./live-refresh";

export const overviewResource = withLiveRefresh(createPollingResource(livekitApi.overview), LIVEKIT_POLL_MS);

const roomResources = new Map<string, PollingResource<LiveKitRoomDetail>>();

/** One live resource per room, created when its sheet first opens. */
export function roomResource(name: string): PollingResource<LiveKitRoomDetail> {
  let resource = roomResources.get(name);
  if (!resource) {
    resource = withLiveRefresh(
      createPollingResource(() => livekitApi.room(name)),
      LIVEKIT_POLL_MS,
    );
    roomResources.set(name, resource);
  }
  return resource;
}

/** Runs a server action; on failure shows an error toast and resolves to false. */
async function attempt(task: () => Promise<void>, failure: string): Promise<boolean> {
  try {
    await task();
    return true;
  } catch (error) {
    toast.error(failure, { description: errorMessage(error) });
    return false;
  }
}

/** Ends a room for everyone, drops it from the overview at once, then re-reads the server. */
export async function endRoom(room: LiveKitRoom) {
  const ended = await attempt(async () => {
    await livekitApi.endRoom(room.name);
    overviewResource.update((data: LiveKitOverview) => ({
      ...data,
      rooms: data.rooms.filter((item) => item.name !== room.name),
    }));
    void overviewResource.refresh();
  }, "Не удалось завершить комнату");
  if (ended) toast.success("Комната завершена", { description: room.title });
  return ended;
}

/** Disconnects one participant; they can rejoin unless the backend also revokes their token. */
export async function removeParticipant(name: string, participant: LiveKitParticipant) {
  const removed = await attempt(async () => {
    await livekitApi.removeParticipant(name, participant.identity);
    roomResources.get(name)?.update((room) => {
      const participants = room.participants.filter((item) => item.identity !== participant.identity);
      return { ...room, participants, num_participants: participants.length };
    });
    overviewResource.update((data) => ({
      ...data,
      rooms: data.rooms.map((room) =>
        room.name === name ? { ...room, num_participants: Math.max(0, room.num_participants - 1) } : room,
      ),
    }));
  }, "Не удалось отключить участника");
  if (removed) toast.success("Участник отключён", { description: participant.name });
  return removed;
}
