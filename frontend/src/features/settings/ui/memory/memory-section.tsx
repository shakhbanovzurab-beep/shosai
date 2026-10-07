import { useTranslations } from "next-intl";

import type { UserSettings } from "../../domain/settings-contract";
import { SettingSwitch } from "../setting-switch";
import { SettingsGroup } from "../settings-row";
import { MemorySummaryRow } from "./memory-summary-row";

export function MemorySection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsMemory");
  return (
    <SettingsGroup>
      <SettingSwitch settings={settings} field="memory_enabled" title={t("memory")} description={t("memoryHint")} />
      <MemorySummaryRow />
    </SettingsGroup>
  );
}
