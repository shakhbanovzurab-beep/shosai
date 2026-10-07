"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";

import { DEMO_USER } from "../data/demo-user";
import { comboKeys, effectiveBindings, type HotkeyId } from "../domain/hotkeys";
import { settingsResource } from "./settings-resources";
import { useIsMac } from "./use-is-mac";

/** Settings › Leo › Voice mode. Assumed on (the default) until settings have loaded. */
export function useVoiceModeEnabled() {
  const settings = usePollingResource(settingsResource);
  return settings.status === "ready" ? settings.data.voice_mode : true;
}

/** Settings › Leo › Response language: a language code, or "auto" (also until settings have loaded). */
export function useResponseLanguageSetting(): string {
  const settings = usePollingResource(settingsResource);
  return settings.status === "ready" ? settings.data.response_language : "auto";
}

/**
 * The signed-in user as the user menu shows them. Once settings load, the photo and name the user set
 * there; until then, the demo user's. The email always comes from the sign-in.
 */
export function useAccountProfile(): { name: string; email: string; avatar: string } {
  const settings = usePollingResource(settingsResource);
  const saved = settings.status === "ready" ? settings.data : null;
  return {
    name: saved?.full_name ?? DEMO_USER.name,
    email: DEMO_USER.email,
    // A loaded profile without a photo shows initials rather than the demo picture.
    avatar: saved ? (saved.avatar_url ?? "") : DEMO_USER.avatar,
  };
}

/**
 * A desktop shortcut as the user set it in Settings › Hotkeys (the default until settings load), as
 * keys to draw, e.g. ["⌥", "⌘", "X"]; null when the user turned it off. `mac` overrides the browser's
 * own platform, e.g. with the system the server detected.
 */
export function useDesktopShortcut(id: HotkeyId, mac?: boolean) {
  const settings = usePollingResource(settingsResource);
  const browserIsMac = useIsMac();
  const isMac = mac ?? browserIsMac;
  const combo = effectiveBindings(settings.status === "ready" ? settings.data.hotkeys : {})[id];
  return combo ? comboKeys(combo, isMac) : null;
}
