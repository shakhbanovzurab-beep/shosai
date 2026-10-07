"use client";

import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { settingsApi } from "../api/settings-api";
import { DATA_KINDS, type DataItemsResponse, type DataKind } from "../domain/data-contract";

export const settingsResource = createPollingResource(settingsApi.get);
export const billingResource = createPollingResource(settingsApi.billing);
export const usageResource = createPollingResource(settingsApi.usage);
/** Privacy › Your data lists, one resource per kind so each loads when its dialog opens. */
export const dataResources = Object.fromEntries(
  DATA_KINDS.map((kind) => [kind, createPollingResource(() => settingsApi.listData(kind))]),
) as Record<DataKind, PollingResource<DataItemsResponse>>;
export const mcpResource = createPollingResource(settingsApi.listMcp);
export const memorySummaryResource = createPollingResource(settingsApi.memorySummary);
export const connectorsResource = createPollingResource(settingsApi.listConnectors);
