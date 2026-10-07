"use client";

import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { ModelPicker, useStudioModels } from "@/features/studio";

import type { UserSettings } from "../../domain/settings-contract";
import { saveSettings } from "../../model/account-actions";
import { SettingsRow } from "../settings-row";

/** Which model Leo answers with: Auto, or any text model on the subscription. */
export function LeoModelRow({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsLeo");
  const words = useTranslations("settings");
  const models = useStudioModels();
  const textModels = models.status === "ready" ? models.data.models.filter((m) => m.capabilities.includes("text")) : [];
  const auto = [{ id: "auto", label: t("model.auto"), hint: t("model.autoHint") }];

  return (
    <SettingsRow title={t("model.title")} description={t("model.description")} htmlFor="leo-model">
      <div className="w-full sm:w-64">
        {models.status === "loading" ? (
          <Skeleton className="h-9 w-full" />
        ) : (
          <ModelPicker
            id="leo-model"
            label={t("model.label")}
            models={textModels}
            options={auto}
            value={settings.leo_model}
            onChange={(id) => void saveSettings({ leo_model: id }, words).catch(() => undefined)}
          />
        )}
      </div>
    </SettingsRow>
  );
}
