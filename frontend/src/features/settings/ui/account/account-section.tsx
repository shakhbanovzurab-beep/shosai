"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Me } from "@/features/identity/domain/session";

import { isWorkRole, WORK_ROLES } from "../../domain/settings-contract";
import { saveProfileField } from "../../model/account-actions";
import { SettingsGroup, SettingsRow } from "../settings-row";
import { AutosaveInput } from "./autosave-input";
import { AvatarEditor } from "./avatar-editor";
import { DeleteAccount } from "./delete-account";
import { Devices } from "./devices";
import { TimeZoneField } from "./time-zone-field";

/** Settings › Account: профиль, фото, устройства и удаление — всё из identity (`/v1/me*`). */
export function AccountSection({ me }: { me: Me }) {
  const t = useTranslations("settings");
  return (
    <div className="flex flex-col gap-6">
      <AvatarEditor me={me} />
      <SettingsGroup title={t("profile.title")}>
        <SettingsRow title={t("profile.email")} description={t("profile.emailHint")}>
          <span dir="auto" className="text-muted-foreground text-sm">
            {me.email}
          </span>
        </SettingsRow>
        <SettingsRow title={t("profile.fullName")} htmlFor="settings-full-name">
          <AutosaveInput id="settings-full-name" field="full_name" initialValue={me.full_name} />
        </SettingsRow>
        <SettingsRow
          title={t("profile.displayName")}
          description={t("profile.displayNameHint")}
          htmlFor="settings-display-name"
        >
          <AutosaveInput id="settings-display-name" field="display_name" initialValue={me.display_name ?? ""} />
        </SettingsRow>
        <SettingsRow title={t("profile.workRole")} description={t("profile.workRoleHint")} htmlFor="settings-work-role">
          <Select
            value={me.work_role ?? undefined}
            onValueChange={(value) => {
              if (isWorkRole(value)) void saveProfileField({ work_role: value }, t).catch(() => undefined);
            }}
          >
            <SelectTrigger id="settings-work-role" className="w-full sm:w-64">
              <SelectValue placeholder={t("profile.workRolePlaceholder")} />
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
        <SettingsRow title={t("profile.timeZone")} description={t("profile.timeZoneHint")} htmlFor="settings-time-zone">
          <TimeZoneField id="settings-time-zone" me={me} />
        </SettingsRow>
      </SettingsGroup>
      <Devices />
      <DeleteAccount email={me.email} />
    </div>
  );
}
