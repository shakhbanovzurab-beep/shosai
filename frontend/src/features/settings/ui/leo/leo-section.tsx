"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { LANGUAGES } from "@/lib/language";

import type { LeoSettings, LeoSettingsPatch } from "../../domain/leo-settings-contract";
import { RESPONSE_LENGTHS } from "../../domain/settings-contract";
import { saveLeoSettings } from "../../model/leo-settings";
import { SettingSwitch } from "../setting-switch";
import { SettingsGroup, SettingsRow } from "../settings-row";
import { LeoModelRow } from "./leo-model-row";

export function LeoSection({ settings }: { settings: LeoSettings }) {
  const t = useTranslations("settingsLeo");
  const words = useTranslations("settings");
  const save = (patch: LeoSettingsPatch) => void saveLeoSettings(patch, words("saveFailed")).catch(() => undefined);

  return (
    <div className="flex flex-col gap-6">
      <SettingsGroup title={t("answers")}>
        <LeoModelRow settings={settings} />
        <SettingsRow title={t("language.title")} description={t("language.description")} htmlFor="leo-language">
          <Select value={settings.response_language} onValueChange={(value) => save({ response_language: value })}>
            <SelectTrigger id="leo-language" className="w-full sm:w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-72">
              <SelectGroup>
                <SelectItem value="auto">{t("language.auto")}</SelectItem>
                {/* Each language by its own name, as in the language menu: names aren't translated. */}
                {LANGUAGES.map((language) => (
                  <SelectItem key={language.code} value={language.code}>
                    <span lang={language.code} dir="auto">
                      {language.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </SettingsRow>
        <SettingsRow title={t("length.title")} description={t("length.description")}>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            spacing={0}
            value={settings.response_length}
            aria-label={t("length.title")}
            onValueChange={(value) => {
              const length = RESPONSE_LENGTHS.find((l) => l === value);
              if (length) save({ response_length: length });
            }}
          >
            {RESPONSE_LENGTHS.map((length) => (
              <ToggleGroupItem key={length} value={length} className="px-3">
                {t(`length.options.${length}`)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </SettingsRow>
      </SettingsGroup>
      <section aria-labelledby="leo-advanced" className="flex flex-col">
        <h3 id="leo-advanced" className="font-medium">
          {t("advanced.title")}
        </h3>
        <p className="text-muted-foreground text-sm">{t("advanced.description")}</p>
        <div className="divide-y">
          <SettingSwitch
            id="setting-web_search"
            checked={settings.web_search}
            onCheckedChange={(checked) => save({ web_search: checked })}
            title={t("advanced.webSearch")}
            description={t("advanced.webSearchHint")}
          />
          <SettingSwitch
            id="setting-voice_mode"
            checked={settings.voice_mode}
            onCheckedChange={(checked) => save({ voice_mode: checked })}
            title={t("advanced.voiceMode")}
            description={t("advanced.voiceModeHint")}
          />
          <SettingSwitch
            id="setting-knowledge_base_search"
            checked={settings.knowledge_base_search}
            onCheckedChange={(checked) => save({ knowledge_base_search: checked })}
            title={t("advanced.knowledgeSearch")}
            description={t("advanced.knowledgeSearchHint")}
          />
          <SettingSwitch
            id="setting-connected_services_search"
            checked={settings.connected_services_search}
            onCheckedChange={(checked) => save({ connected_services_search: checked })}
            title={t("advanced.connectedSearch")}
            description={t("advanced.connectedSearchHint")}
          />
        </div>
      </section>
    </div>
  );
}
