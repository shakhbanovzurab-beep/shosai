"use client";

import { RotateCcw } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { effectiveBindings, HOTKEY_COMMANDS, type HotkeyBindings, type HotkeyId } from "../../domain/hotkeys";
import type { UserSettings } from "../../domain/settings-contract";
import { saveSettings } from "../../model/account-actions";
import { HotkeyRow } from "./hotkey-row";

/** Settings › Hotkeys: the desktop app's global shortcuts. Click a key box to record a new one. */
export function HotkeysSection({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settingsHotkeys");
  const words = useTranslations("settings");
  const save = (hotkeys: HotkeyBindings) => void saveSettings({ hotkeys }, words).catch(() => undefined);
  const saved = settings.hotkeys;
  const bindings = effectiveBindings(saved);

  function change(id: HotkeyId, combo: string | null, fallback: string) {
    const rest = Object.fromEntries(Object.entries(saved).filter(([key]) => key !== id)) as HotkeyBindings;
    // Back on the default means "not customized", so a later change of the default reaches this user too.
    save(combo === fallback ? rest : { ...rest, [id]: combo });
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">{t("description")}</p>
      <div className="divide-y overflow-hidden rounded-xl border bg-card">
        {HOTKEY_COMMANDS.map((command) => (
          <HotkeyRow
            key={command.id}
            id={command.id}
            combo={bindings[command.id]}
            bindings={bindings}
            customized={command.id in saved}
            onChange={(combo) => change(command.id, combo, command.default)}
            onReset={() => change(command.id, command.default, command.default)}
          />
        ))}
      </div>
      {Object.keys(saved).length > 0 ? (
        <div>
          <Button variant="outline" size="sm" onClick={() => save({})}>
            <RotateCcw data-icon="inline-start" />
            {t("resetAll")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
