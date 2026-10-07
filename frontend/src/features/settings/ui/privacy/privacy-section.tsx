import { useTranslations } from "next-intl";

import type { UserSettings } from "../../domain/settings-contract";
import { SettingSwitch } from "../setting-switch";
import { SettingsGroup } from "../settings-row";
import { YourData } from "./your-data";

export function PrivacySection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsPrivacy");
  return (
    <div className="flex flex-col gap-6">
      <SettingsGroup title={t("data")}>
        <SettingSwitch
          settings={settings}
          field="improve_models"
          title={t("improveModels")}
          description={t("improveModelsHint")}
        />
        <SettingSwitch
          settings={settings}
          field="share_location"
          title={t("shareLocation")}
          description={t("shareLocationHint")}
        />
      </SettingsGroup>
      <YourData />
    </div>
  );
}
