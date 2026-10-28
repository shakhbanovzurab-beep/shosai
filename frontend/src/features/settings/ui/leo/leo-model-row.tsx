"use client";

import { useTranslations } from "use-intl";

import { useStudioModels } from "@/features/studio/model/studio-resources";
import { ModelPicker } from "@/features/studio/ui/model-picker";

import type { LeoSettings } from "../../domain/leo-settings-contract";
import { saveLeoSettings } from "../../model/leo-settings";
import { SettingsRow } from "../settings-row";

const AUTO = "auto";

/**
 * Модель ответов Leo: «Авто» или модель из каталога, которую предлагает тариф человека (studio, шаг 11).
 * Сохранённая модель, которой тариф больше не предлагает, показывается как «Авто» с пометкой: так и отвечает Leo.
 */
export function LeoModelRow({ settings }: { settings: LeoSettings }) {
  const t = useTranslations("settingsLeo");
  const words = useTranslations("settings");
  const offered = useStudioModels();
  const models = offered.status === "ready" ? offered.data.models.filter((m) => m.capabilities.includes("text")) : [];
  const gone =
    offered.status === "ready" && settings.leo_model !== AUTO && !models.some((m) => m.id === settings.leo_model);
  const auto = [{ id: AUTO, label: t("model.auto"), hint: t("model.autoHint") }];

  return (
    <SettingsRow title={t("model.title")} description={t("model.description")} htmlFor="leo-model">
      <div className="flex w-full flex-col gap-1.5 sm:w-64">
        <ModelPicker
          id="leo-model"
          label={t("model.label")}
          models={models}
          options={auto}
          value={gone ? AUTO : settings.leo_model}
          onChange={(id) => void saveLeoSettings({ leo_model: id }, words("saveFailed")).catch(() => undefined)}
        />
        {gone ? <p className="text-muted-foreground text-xs">{t("model.gone")}</p> : null}
      </div>
    </SettingsRow>
  );
}
