import { useTranslations } from "use-intl";

import type { Me } from "@/features/identity/domain/session";

import { SettingsGroup } from "../settings-row";
import { ConsentSetting } from "./consent-setting";
import { ConsentSwitch } from "./consent-switch";
import { YourData } from "./your-data";

/**
 * Settings › Privacy: согласия из identity (`PATCH /v1/me`), cookie аналитики и выгрузка всех данных. Согласие на
 * обработку в ЕС спрашивается только у аккаунта в российском доме — у остальных данные и так в ЕС.
 */
export function PrivacySection({ me }: { me: Me }) {
  const t = useTranslations("settingsPrivacy");
  return (
    <div className="flex flex-col gap-6">
      <SettingsGroup title={t("data")}>
        {me.home === "ru" ? (
          <ConsentSwitch me={me} kind="cross_border" title={t("crossBorder")} description={t("crossBorderHint")} />
        ) : null}
        <ConsentSwitch me={me} kind="improve_models" title={t("improveModels")} description={t("improveModelsHint")} />
        <ConsentSwitch me={me} kind="share_location" title={t("shareLocation")} description={t("shareLocationHint")} />
        <ConsentSwitch me={me} kind="marketing" title={t("marketing")} description={t("marketingHint")} />
      </SettingsGroup>
      <ConsentSetting />
      <YourData />
    </div>
  );
}
