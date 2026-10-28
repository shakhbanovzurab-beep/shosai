"use client";

import { createPollingResource } from "@/lib/polling-resource";

import { connectorsApi } from "../api/connectors-api";
import { settingsApi } from "../api/settings-api";

export const settingsResource = createPollingResource(settingsApi.get);
export const billingResource = createPollingResource(settingsApi.billing);
export const usageResource = createPollingResource(settingsApi.usage);
export const mcpResource = createPollingResource(settingsApi.listMcp);
export const connectorsResource = createPollingResource(connectorsApi.list);
