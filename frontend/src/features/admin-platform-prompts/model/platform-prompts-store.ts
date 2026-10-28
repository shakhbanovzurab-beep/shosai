"use client";

import { createPollingResource } from "@/lib/polling-resource";

import { platformPromptsApi } from "../api/platform-prompts-api";

/** Черновик и действующая версия: читаются при открытии экрана и по просьбе, без опроса. */
export const platformPromptsResource = createPollingResource(platformPromptsApi.get);
