"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { apiErrorDescription } from "@/lib/api/error-description";
import { createPollingResource } from "@/lib/polling-resource";

import { leoSettingsApi } from "../api/leo-settings-api";
import type { LeoSettings, LeoSettingsPatch } from "../domain/leo-settings-contract";

/** Settings › Leo, read once and shared by the settings dialog and the panel. */
export const leoSettingsResource = createPollingResource(leoSettingsApi.get);

/** Settings › Leo › Voice mode. Assumed on (the default) until the settings have loaded. */
export function useVoiceModeEnabled() {
  const settings = usePollingResource(leoSettingsResource);
  return settings.status === "ready" ? settings.data.voice_mode : true;
}

/** Settings › Leo › Response language: a language code, or "auto" (also until the settings have loaded). */
export function useResponseLanguageSetting(): string {
  const settings = usePollingResource(leoSettingsResource);
  return settings.status === "ready" ? settings.data.response_language : "auto";
}

/** Saves a change right away: shown at once, the server's answer kept, the old value back if it refuses. */
export async function saveLeoSettings(patch: LeoSettingsPatch, failed: string) {
  const before = leoSettingsResource.getSnapshot();
  leoSettingsResource.update((data): LeoSettings => ({ ...data, ...definedOnly(patch) }));
  try {
    const saved = await leoSettingsApi.patch(patch);
    leoSettingsResource.update(() => saved);
  } catch (error) {
    if (before.status === "ready") leoSettingsResource.update(() => before.data);
    toast.error(failed, { description: apiErrorDescription(error) });
    throw error;
  }
}

/** The fields the change names: an absent or `null` field leaves the shown value as it is. */
function definedOnly(patch: LeoSettingsPatch): Partial<LeoSettings> {
  return Object.fromEntries(Object.entries(patch).filter(([, value]) => value !== null && value !== undefined));
}
