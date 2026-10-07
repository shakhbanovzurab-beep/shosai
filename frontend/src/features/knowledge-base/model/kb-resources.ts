"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { kbApi } from "../api/kb-api";
import { BUSY_CONNECTOR } from "../domain/contract";

export const indexResource = createPollingResource(kbApi.index);

export const connectorsResource = createPollingResource(kbApi.listConnectors, (data) =>
  data.connectors.some((connector) => BUSY_CONNECTOR.has(connector.status)),
);

export const useIndex = () => usePollingResource(indexResource);
export const useConnectors = () => usePollingResource(connectorsResource);
