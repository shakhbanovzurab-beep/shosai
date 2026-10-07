"use client";

import { createPollingResource } from "@/lib/polling-resource";

import { platformPromptsApi } from "../api/platform-prompts-api";

export const platformPromptsResource = createPollingResource(platformPromptsApi.get);
