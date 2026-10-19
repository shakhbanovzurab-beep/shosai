import { useTranslations } from "use-intl";

import type { UserSettings } from "../../domain/settings-contract";
import { SettingSwitch } from "../setting-switch";
import { SettingsGroup } from "../settings-row";
import { MemoryFactsRow } from "./memory-facts-row";
import { MemorySummaryRow } from "./memory-summary-row";

export function MemorySection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsMemory");
  return (
    <SettingsGroup>
      <SettingSwitch settings={settings} field="memory_enabled" title={t("memory")} description={t("memoryHint")} />
      <MemorySummaryRow />
      <MemoryFactsRow memoryOn={settings.memory_enabled} />
    </SettingsGroup>
  );
}
