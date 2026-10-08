"use client";

import { Settings } from "lucide-react";
import { useTranslations } from "use-intl";
import { useShallow } from "zustand/react/shallow";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { THEME_PRESET_OPTIONS, type ThemePreset } from "@/lib/preferences/theme";

import { type FontKey, fontOptions } from "../domain/fonts";
import { usePreferencesStore } from "../model/preferences-provider";
import { PreferenceToggle } from "./preference-toggle";

/** The header's layout settings, in the interface language (Russian in the admin panel). */
export function LayoutControls() {
  const t = useTranslations("layoutControls");
  const { values, resolvedThemeMode, setPreference, resetPreferences } = usePreferencesStore(
    useShallow((state) => ({
      values: state.values,
      resolvedThemeMode: state.resolvedThemeMode,
      setPreference: state.setPreference,
      resetPreferences: state.resetPreferences,
    })),
  );

  // Typed handlers: the Select reports its value as the option's string key.
  const onPresetChange = (preset: ThemePreset) => setPreference("theme_preset", preset);
  const onFontChange = (font: FontKey) => setPreference("font", font);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t("layoutSettings")}>
          <Settings className="size-5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end">
        <div className="flex flex-col gap-5">
          <div className="space-y-1.5">
            <h4 className="font-medium text-sm leading-none">{t("preferences")}</h4>
            <p className="text-muted-foreground text-xs">{t("preferencesHint")}</p>
          </div>
          <div className="space-y-3 **:data-[slot=toggle-group]:w-full **:data-[slot=toggle-group-item]:flex-1 **:data-[slot=toggle-group-item]:text-xs">
            <div className="space-y-1">
              <Label className="font-medium text-xs">{t("themePreset")}</Label>
              <Select value={values.theme_preset} onValueChange={onPresetChange}>
                <SelectTrigger size="sm" className="w-full text-xs">
                  <SelectValue placeholder={t("presetPlaceholder")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {THEME_PRESET_OPTIONS.map((preset) => (
                      <SelectItem key={preset.value} className="text-xs" value={preset.value}>
                        <span
                          className="size-2.5 rounded-full"
                          style={{
                            backgroundColor: resolvedThemeMode === "dark" ? preset.primary.dark : preset.primary.light,
                          }}
                        />
                        {preset.value === "default" ? t("defaultPreset") : preset.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label className="font-medium text-xs">{t("fonts")}</Label>
              <Select value={values.font} onValueChange={onFontChange}>
                <SelectTrigger size="sm" className="w-full text-xs">
                  <SelectValue placeholder={t("fontPlaceholder")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {fontOptions.map((option) => (
                      <SelectItem key={option.key} className="text-xs" value={option.key}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <PreferenceToggle
              label={t("themeMode")}
              value={values.theme_mode}
              onChange={(mode) => setPreference("theme_mode", mode)}
              options={[
                { value: "light", label: t("light") },
                { value: "dark", label: t("dark") },
                { value: "system", label: t("system") },
              ]}
            />
            <PreferenceToggle
              label={t("pageLayout")}
              value={values.content_layout}
              onChange={(layout) => setPreference("content_layout", layout)}
              options={[
                { value: "centered", label: t("centered") },
                { value: "full-width", label: t("fullWidth") },
              ]}
            />
            <PreferenceToggle
              label={t("navbarBehavior")}
              value={values.navbar_style}
              onChange={(style) => setPreference("navbar_style", style)}
              options={[
                { value: "sticky", label: t("sticky") },
                { value: "scroll", label: t("scroll") },
              ]}
            />
            <PreferenceToggle
              label={t("sidebarStyle")}
              value={values.sidebar_variant}
              onChange={(variant) => setPreference("sidebar_variant", variant)}
              options={[
                { value: "inset", label: t("inset") },
                { value: "sidebar", label: t("sidebar") },
                { value: "floating", label: t("floating") },
              ]}
            />
            <PreferenceToggle
              label={t("collapseMode")}
              value={values.sidebar_collapsible}
              onChange={(mode) => setPreference("sidebar_collapsible", mode)}
              options={[
                { value: "icon", label: t("icon") },
                { value: "offcanvas", label: t("offcanvas") },
              ]}
            />

            <Button type="button" size="sm" variant="outline" className="w-full text-xs" onClick={resetPreferences}>
              {t("restore")}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
