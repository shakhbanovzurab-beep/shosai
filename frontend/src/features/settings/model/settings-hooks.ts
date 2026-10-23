"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";

import { comboKeys, effectiveBindings, type HotkeyId } from "../domain/hotkeys";
import { settingsResource } from "./settings-resources";
import { useIsMac } from "./use-is-mac";

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
