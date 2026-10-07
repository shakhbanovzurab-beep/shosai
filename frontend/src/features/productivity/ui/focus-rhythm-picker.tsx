"use client";

import { useFormatter, useTranslations } from "next-intl";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { FOCUS_PRESETS, type FocusPreset } from "../domain/focus/timer";
import { focusActions } from "../model/focus-store";
import { presetHint, presetName } from "../model/words";

/** The rhythm switcher ("25/5", "50/10"…), each explained in a tooltip. Locked while the timer runs. */
export function FocusRhythmPicker({ value, disabled }: { value: FocusPreset["id"]; disabled: boolean }) {
  const t = useTranslations("productivityFocus");
  const format = useFormatter();

  return (
    <ToggleGroup
      type="single"
      variant="outline"
      size="sm"
      spacing={0}
      value={value}
      disabled={disabled}
      onValueChange={(id) => {
        const next = FOCUS_PRESETS.find((p) => p.id === id);
        if (next) focusActions.choose(next.id);
      }}
      aria-label={t("rhythm")}
      className="w-full"
    >
      {/* The tooltip trigger takes over `data-state`, so the selected item is styled by `aria-checked`. */}
      {FOCUS_PRESETS.map((preset) => {
        const name = presetName(t, preset);
        const hint = presetHint(t, format, preset);
        return (
          <Tooltip key={preset.id}>
            <TooltipTrigger asChild>
              <ToggleGroupItem
                value={preset.id}
                aria-label={t("presetLabel", { name, hint })}
                className="flex-1 px-0 text-muted-foreground tabular-nums aria-checked:bg-muted aria-checked:font-semibold aria-checked:text-foreground disabled:aria-checked:opacity-100"
              >
                {preset.label}
              </ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent className="max-w-60">
              {t.rich("presetTooltip", { name, hint, b: (chunks) => <span className="font-medium">{chunks}</span> })}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </ToggleGroup>
  );
}
