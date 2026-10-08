"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { LANGUAGES } from "@/lib/language";

import { RESPONSE_LENGTHS, type UserSettings } from "../../domain/settings-contract";
import { saveSettings } from "../../model/account-actions";
import { SettingSwitch } from "../setting-switch";
import { SettingsGroup, SettingsRow } from "../settings-row";
import { LeoModelRow } from "./leo-model-row";

export function LeoSection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsLeo");
  const words = useTranslations("settings");
  const save = (patch: Partial<UserSettings>) => void saveSettings(patch, words).catch(() => undefined);

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
            settings={settings}
            field="web_search"
            title={t("advanced.webSearch")}
            description={t("advanced.webSearchHint")}
          />
          <SettingSwitch
            settings={settings}
            field="voice_mode"
            title={t("advanced.voiceMode")}
            description={t("advanced.voiceModeHint")}
          />
          <SettingSwitch
            settings={settings}
            field="knowledge_base_search"
            title={t("advanced.knowledgeSearch")}
            description={t("advanced.knowledgeSearchHint")}
          />
          <SettingSwitch
            settings={settings}
            field="connected_services_search"
            title={t("advanced.connectedSearch")}
            description={t("advanced.connectedSearchHint")}
          />
        </div>
      </section>
    </div>
  );
}
