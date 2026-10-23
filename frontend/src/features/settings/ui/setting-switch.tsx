"use client";

import { Switch } from "@/components/ui/switch";

import { SettingsRow } from "./settings-row";

/** An on/off preference row; the owner of the preference saves it the moment it is flipped. */
export function SettingSwitch({
  id,
  checked,
  onCheckedChange,
  title,
  description,
}: {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  title: string;
  description: React.ReactNode;
}) {
  return (
    <SettingsRow title={title} description={description} htmlFor={id}>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
    </SettingsRow>
  );
}
