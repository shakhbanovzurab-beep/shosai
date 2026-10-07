"use client";

import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { hubApi } from "../api/hub-api";
import type { Hub, HubsResponse } from "../domain/contract";

/*
 * Every server read of the Hub, keyed in this one place: one resource per block, made on first use
 * and kept so going back shows it at once. Nothing else creates requests, so a block never asks
 * per row, and after a change only the affected hub and the brief are read again.
 */

function keyed<T>(load: (key: string) => Promise<T>) {
  const made = new Map<string, PollingResource<T>>();
  return {
    of(key: string) {
      let resource = made.get(key);
      if (!resource) {
        resource = createPollingResource(() => load(key));
        made.set(key, resource);
      }
      return resource;
    },
    /** Only what has been read before; nothing is fetched for screens never opened. */
    loaded: (key: string) => made.get(key) ?? null,
    forget: (key: string) => made.delete(key),
  };
}

export const hubLists = {
  active: createPollingResource(() => hubApi.hubs(false)),
  all: createPollingResource(() => hubApi.hubs(true)),
};

export const hubThreads = keyed((hubId) => hubApi.threads(hubId));
export const threadDetails = keyed((threadId) => hubApi.thread(threadId));
export const hubDigests = keyed((hubId) => hubApi.digest(hubId));
export const hubFeeds = keyed((hubId) => hubApi.feed(hubId, null));
export const hubMaterials = keyed((hubId) => hubApi.materials(hubId));
export const meetingHubs = keyed((meetingId) => hubApi.meetingHub(meetingId));
export const brief = createPollingResource(hubApi.brief);
export const preps = createPollingResource(hubApi.preps);

/** Puts a hub the server just returned into both lists (the active one drops it once archived). */
export function receiveHub(hub: Hub) {
  const replace = (data: HubsResponse, keep: boolean): HubsResponse => {
    const known = data.hubs.some((h) => h.id === hub.id);
    const hubs = known ? data.hubs.map((h) => (h.id === hub.id ? hub : h)) : [hub, ...data.hubs];
    return { hubs: keep ? hubs : hubs.filter((h) => h.id !== hub.id) };
  };
  hubLists.active.update((data) => replace(data, !hub.archived));
  hubLists.all.update((data) => replace(data, true));
}

export function dropHub(hubId: string) {
  const without = (data: HubsResponse) => ({ hubs: data.hubs.filter((h) => h.id !== hubId) });
  hubLists.active.update(without);
  hubLists.all.update(without);
  for (const blocks of [hubThreads, hubDigests, hubFeeds, hubMaterials]) blocks.forget(hubId);
}

/** After a topic changes: its hub's summary, digest and the brief; the rows were already updated in place. */
export function refreshAfterThreadChange(hubId: string, threadId: string) {
  void hubLists.active.refresh();
  if (hubLists.all.getSnapshot().status === "ready") void hubLists.all.refresh();
  void hubDigests.loaded(hubId)?.refresh();
  void threadDetails.loaded(threadId)?.refresh();
  void brief.refresh();
  void preps.refresh();
}

/** After a meeting is filed or taken out: the hub's counts, its feed and digest. */
export function refreshAfterFiling(hubId: string) {
  void hubLists.active.refresh();
  void hubFeeds.loaded(hubId)?.refresh();
  void hubDigests.loaded(hubId)?.refresh();
  void hubThreads.loaded(hubId)?.refresh();
}
