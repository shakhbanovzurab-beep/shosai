import { useTranslations } from "use-intl";

import { Switch } from "@/components/ui/switch";
import { decideConsent, tagManagerConfigured, useConsent } from "@/features/consent/model/consent-store";

import { SettingsGroup, SettingsRow } from "../settings-row";

/** Согласие на cookie аналитики и маркетинга: отозвать его так же просто, как дать (ADR 0045). */
export function ConsentSetting() {
  const choice = useConsent();
  const t = useTranslations("consent");
  if (!tagManagerConfigured) return null;
  return (
    <SettingsGroup title={t("settingsGroup")}>
      <SettingsRow title={t("settingTitle")} description={t("settingHint")} htmlFor="setting-consent">
        <Switch
          id="setting-consent"
          checked={choice === "granted"}
          onCheckedChange={(checked) => decideConsent(checked ? "granted" : "denied")}
        />
      </SettingsRow>
    </SettingsGroup>
  );
}
