"use client";

import { useSyncExternalStore } from "react";

import type { ResourceState } from "@/lib/polling-resource";

import type { HubRef, HubsResponse } from "../domain/contract";
import { HUBS_PATH } from "../domain/paths";
import { hubLists } from "./resources";

const NONE: ResourceState<HubsResponse> = { status: "loading" };
/** Nothing to listen to outside a hub's page. */
const stopListening = () => undefined;
const idle = () => stopListening;
const none = () => NONE;

/** The hub id in a path like /app/hub/<id>, or null. */
export const hubIdFromPath = (pathname: string) =>
  pathname.startsWith(`${HUBS_PATH}/`) ? decodeURIComponent(pathname.slice(HUBS_PATH.length + 1).split("/")[0]) : null;

/**
 * The hub whose page is open, for the assistant to work inside it. It reads the list the page already
 * loaded, so it costs no extra request; elsewhere it reads nothing.
 */
export function useHubFromPath(pathname: string): HubRef | null {
  const id = hubIdFromPath(pathname);
  const list = useSyncExternalStore(id ? hubLists.all.subscribe : idle, id ? hubLists.all.getSnapshot : none, none);
  const hub = id && list.status === "ready" ? list.data.hubs.find((h) => h.id === id) : undefined;
  return hub ? { id: hub.id, name: hub.name } : null;
}
