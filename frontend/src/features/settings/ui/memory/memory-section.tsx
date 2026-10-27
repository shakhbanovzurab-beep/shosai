import { useTranslations } from "use-intl";

import { turnMemory, useMemorySwitch } from "@/features/memory/model/memory-switch";

import { SettingSwitch } from "../setting-switch";
import { SettingsGroup } from "../settings-row";
import { MemoryFactsRow } from "./memory-facts-row";
import { MemorySummaryRow } from "./memory-summary-row";

/** Настройки › Память: переключатель — у слайса `memory` (`/v1/agent/memory/settings`), сводка и факты. */
export function MemorySection() {
  const t = useTranslations("settingsMemory");
  const words = useTranslations("settings");
  const memory = useMemorySwitch();
  return (
    <SettingsGroup>
      <SettingSwitch
        id="setting-memory_enabled"
        checked={memory.status === "ready" && memory.data}
        onCheckedChange={(checked) => void turnMemory(checked, words("saveFailed"))}
        title={t("memory")}
        description={t("memoryHint")}
      />
      <MemorySummaryRow />
      <MemoryFactsRow />
    </SettingsGroup>
  );
}
