import { useTranslations } from "use-intl";

import type { UserSettings } from "../../domain/settings-contract";
import { saveSettings } from "../../model/account-actions";
import { SettingSwitch } from "../setting-switch";
import { SettingsGroup } from "../settings-row";
import { MemoryFactsRow } from "./memory-facts-row";
import { MemorySummaryRow } from "./memory-summary-row";

export function MemorySection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsMemory");
  const words = useTranslations("settings");
  return (
    <SettingsGroup>
      <SettingSwitch
        id="setting-memory_enabled"
        checked={settings.memory_enabled}
        onCheckedChange={(checked) => void saveSettings({ memory_enabled: checked }, words).catch(() => undefined)}
        title={t("memory")}
        description={t("memoryHint")}
      />
      <MemorySummaryRow />
      <MemoryFactsRow memoryOn={settings.memory_enabled} />
    </SettingsGroup>
  );
}
