"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";

import { hubApi } from "../api/hub-api";
import type { FeedPage, Loaded } from "../domain/contract";
import {
  brief,
  hubDigests,
  hubFeeds,
  hubLists,
  hubMaterials,
  hubThreads,
  meetingHubs,
  preps,
  threadDetails,
} from "./resources";

/* What screens read. Each hook is one block's single request; screens never fetch on their own. */

export const useHubList = (includeArchived: boolean) =>
  usePollingResource(includeArchived ? hubLists.all : hubLists.active);
export const useHubThreads = (hubId: string) => usePollingResource(hubThreads.of(hubId));
export const useThreadDetail = (threadId: string) => usePollingResource(threadDetails.of(threadId));
export const useDigest = (hubId: string) => usePollingResource(hubDigests.of(hubId));
export const useFeed = (hubId: string) => usePollingResource(hubFeeds.of(hubId));
export const useMaterials = (hubId: string) => usePollingResource(hubMaterials.of(hubId));
export const useMeetingHub = (meetingId: string) => usePollingResource(meetingHubs.of(meetingId));
export const useBrief = () => usePollingResource(brief);
export const usePreps = () => usePollingResource(preps);

/** Starts loading a topic before it's opened (hover or focus on desktop), so the panel opens filled. */
export const preloadThread = (threadId: string) => {
  const resource = threadDetails.of(threadId);
  if (resource.getSnapshot().status === "loading") void resource.refresh();
};

export const retry = {
  hubs: () => Promise.all([hubLists.active.refresh(), hubLists.all.refresh()]),
  threads: (hubId: string) => hubThreads.of(hubId).refresh(),
  thread: (threadId: string) => threadDetails.of(threadId).refresh(),
  digest: (hubId: string) => hubDigests.of(hubId).refresh(),
  feed: (hubId: string) => hubFeeds.of(hubId).refresh(),
  materials: (hubId: string) => hubMaterials.of(hubId).refresh(),
  meetingHub: (meetingId: string) => meetingHubs.of(meetingId).refresh(),
  brief: () => brief.refresh(),
  preps: () => preps.refresh(),
};

/** Earlier meetings of the feed, a page at a time; resolves to whether it worked. */
export async function loadEarlier(hubId: string, cursor: string) {
  try {
    const next = await hubApi.feed(hubId, cursor);
    hubFeeds.of(hubId).update(
      (page: Loaded<FeedPage>): Loaded<FeedPage> => ({
        partial: page.partial || next.partial,
        data: { meetings: [...page.data.meetings, ...next.data.meetings], nextCursor: next.data.nextCursor },
      }),
    );
    return true;
  } catch {
    return false;
  }
}
