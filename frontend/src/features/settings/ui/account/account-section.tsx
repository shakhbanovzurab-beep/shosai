"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { isWorkRole, type UserSettings, WORK_ROLES } from "../../domain/settings-contract";
import { saveSettings } from "../../model/account-actions";
import { SettingsGroup, SettingsRow } from "../settings-row";
import { AutosaveInput } from "./autosave-input";
import { AvatarEditor } from "./avatar-editor";
import { DeleteAccount } from "./delete-account";

export function AccountSection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settings");
  return (
    <div className="flex flex-col gap-6">
      <AvatarEditor settings={settings} />
      <SettingsGroup title={t("profile.title")}>
        <SettingsRow title={t("profile.email")} description={t("profile.emailHint")}>
          <span dir="auto" className="text-muted-foreground text-sm">
            {settings.email}
          </span>
        </SettingsRow>
        <SettingsRow title={t("profile.fullName")} htmlFor="settings-full-name">
          <AutosaveInput id="settings-full-name" field="full_name" initialValue={settings.full_name} />
        </SettingsRow>
        <SettingsRow
          title={t("profile.displayName")}
          description={t("profile.displayNameHint")}
          htmlFor="settings-display-name"
        >
          <AutosaveInput id="settings-display-name" field="display_name" initialValue={settings.display_name} />
        </SettingsRow>
        <SettingsRow title={t("profile.workRole")} description={t("profile.workRoleHint")} htmlFor="settings-work-role">
          <Select
            value={settings.work_role}
            onValueChange={(value) => {
              if (isWorkRole(value)) void saveSettings({ work_role: value }, t).catch(() => undefined);
            }}
          >
            <SelectTrigger id="settings-work-role" className="w-full sm:w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-80">
              <SelectGroup>
                {WORK_ROLES.map((role) => (
                  <SelectItem key={role} value={role}>
                    {t(`workRoles.${role}`)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </SettingsRow>
      </SettingsGroup>
      <DeleteAccount email={settings.email} />
    </div>
  );
}
