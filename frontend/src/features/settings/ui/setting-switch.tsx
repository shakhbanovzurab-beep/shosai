"use client";

import { useTranslations } from "use-intl";

import { Switch } from "@/components/ui/switch";

import type { UserSettings } from "../domain/settings-contract";
import { saveSettings } from "../model/account-actions";
import { SettingsRow } from "./settings-row";

type BooleanField = { [K in keyof UserSettings]: UserSettings[K] extends boolean ? K : never }[keyof UserSettings];

/** An on/off preference row that saves the moment it is flipped. */
export function SettingSwitch({
  settings,
  field,
  title,
  description,
}: {
  settings: UserSettings;
  field: BooleanField;
  title: string;
  description: React.ReactNode;
}) {
  const t = useTranslations("settings");
  const id = `setting-${field}`;
  return (
    <SettingsRow title={title} description={description} htmlFor={id}>
      <Switch
        id={id}
        checked={settings[field]}
        onCheckedChange={(checked) => void saveSettings({ [field]: checked }, t).catch(() => undefined)}
      />
    </SettingsRow>
  );
}
