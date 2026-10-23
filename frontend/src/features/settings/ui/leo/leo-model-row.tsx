"use client";

import { useTranslations } from "use-intl";

import { ModelPicker } from "@/features/studio/ui/model-picker";

import type { LeoSettings } from "../../domain/leo-settings-contract";
import { saveLeoSettings } from "../../model/leo-settings";
import { SettingsRow } from "../settings-row";

/**
 * Which model Leo answers with. Until studio publishes the plan's models, Auto is the one choice the server
 * accepts (ADR 0068 AG-D4), so the picker offers it alone.
 */
export function LeoModelRow({ settings }: { settings: LeoSettings }) {
  const t = useTranslations("settingsLeo");
  const words = useTranslations("settings");
  const auto = [{ id: "auto", label: t("model.auto"), hint: t("model.autoHint") }];

  return (
    <SettingsRow title={t("model.title")} description={t("model.description")} htmlFor="leo-model">
      <div className="w-full sm:w-64">
        <ModelPicker
          id="leo-model"
          label={t("model.label")}
          models={[]}
          options={auto}
          value={settings.leo_model}
          onChange={(id) => void saveLeoSettings({ leo_model: id }, words("saveFailed")).catch(() => undefined)}
        />
      </div>
    </SettingsRow>
  );
}
