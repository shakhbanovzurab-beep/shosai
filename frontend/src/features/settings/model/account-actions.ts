"use client";

import { toast } from "sonner";

import { clearAvatar, saveProfile, setAvatar } from "@/features/identity/model/profile";
import { formatBytes } from "@/i18n/format-units";
import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";

import { settingsApi } from "../api/settings-api";
import type { SettingsPatch, UserSettings } from "../domain/settings-contract";
import { AVATAR_INPUT_MAX_BYTES, AvatarError, scaleAvatar } from "./scale-avatar";
import { settingsResource } from "./settings-resources";
import type { SettingsWords } from "./words";

/** Saves preference fields right away: shows the change at once and rolls back if the server refuses it. */
export async function saveSettings(patch: SettingsPatch, t: SettingsWords) {
  const before = settingsResource.getSnapshot();
  settingsResource.update((data) => ({ ...data, ...patch }));
  try {
    const saved: UserSettings = await settingsApi.patch(patch);
    settingsResource.update(() => saved);
  } catch (error) {
    if (before.status === "ready") settingsResource.update(() => before.data);
    toast.error(t("saveFailed"), { description: apiErrorDescription(error) });
    throw error;
  }
}

/** Why the browser couldn't prepare the photo, in the interface language; the server's own words otherwise. */
function avatarProblem(error: unknown, t: SettingsWords, locale: string) {
  if (!(error instanceof AvatarError)) return errorMessage(error);
  if (error.problem === "tooLarge") return t("avatar.tooLarge", { size: formatBytes(locale, AVATAR_INPUT_MAX_BYTES) });
  return t(`avatar.${error.problem}`);
}

/** Профиль из Settings › Account (identity, `PATCH /v1/me`): показан сразу, при отказе возвращается прежний. */
export async function saveProfileField(change: Parameters<typeof saveProfile>[0], t: SettingsWords) {
  try {
    await saveProfile(change);
  } catch (error) {
    toast.error(t("saveFailed"), { description: apiErrorDescription(error) });
    throw error;
  }
}

/** Crops and scales the photo in the browser, uploads it and shows the saved one. */
export async function uploadAvatar(file: File, t: SettingsWords, locale: string) {
  try {
    await setAvatar(await scaleAvatar(file));
  } catch (error) {
    toast.error(t("avatar.updateFailed"), { description: avatarProblem(error, t, locale) });
  }
}

export async function removeAvatar(t: SettingsWords) {
  try {
    await clearAvatar();
  } catch (error) {
    toast.error(t("avatar.removeFailed"), { description: apiErrorDescription(error) });
  }
}
