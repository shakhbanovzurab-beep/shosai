"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { settingsApi } from "../api/settings-api";
import { memorySummaryResource } from "./settings-resources";
import type { MemoryWords } from "./words";

/** Asks about the summary or tells Leo what to change; resolves to whether it was sent. */
export async function sendSummaryMessage(message: string, t: MemoryWords) {
  try {
    const summary = await settingsApi.sendSummaryMessage(message);
    memorySummaryResource.update(() => summary);
    return true;
  } catch (error) {
    toast.error(t("composer.sendFailed"), { description: errorMessage(error) });
    return false;
  }
}

/** Has the summary rewritten from the latest memories and chats. */
export async function refreshMemorySummary(t: MemoryWords) {
  try {
    const refreshed = await settingsApi.refreshSummary();
    memorySummaryResource.update(() => refreshed);
  } catch (error) {
    toast.error(t("summary.refreshFailed"), { description: errorMessage(error) });
  }
}
