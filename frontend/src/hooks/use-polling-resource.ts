"use client";

import { useSyncExternalStore } from "react";

import type { PollingResource, ResourceState } from "@/lib/polling-resource";

/** Subscribes a component to a polling resource; it loads on first use and re-renders on every change. */
export function usePollingResource<T>(resource: PollingResource<T>): ResourceState<T> {
  return useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getServerSnapshot);
}
