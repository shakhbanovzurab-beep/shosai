"use client";

import { Captions, Keyboard, Languages, type LucideIcon, Mic, PanelTop } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { type HotkeyId, useDesktopShortcut, useOpenSettings } from "@/features/settings";

const FEATURES = [
  { id: "toggle_recording", icon: Mic },
  { id: "toggle_overlay", icon: PanelTop },
  { id: "live_translation", icon: Languages },
  { id: "prompter", icon: Captions },
] as const satisfies readonly { id: HotkeyId; icon: LucideIcon }[];

function Shortcut({ id, mac }: { id: HotkeyId; mac: boolean | undefined }) {
  const t = useTranslations("download");
  const keys = useDesktopShortcut(id, mac);
  if (!keys) return <span className="text-muted-foreground text-xs">{t("features.shortcutOff")}</span>;
  return (
    <KbdGroup aria-label={t("features.shortcut", { keys: keys.join(" ") })}>
      {keys.map((key) => (
        <Kbd key={key}>{key}</Kbd>
      ))}
    </KbdGroup>
  );
}

/** What the desktop app adds, each with its global shortcut as the user set it in Settings › Hotkeys. */
export function DesktopFeatures({
  mac,
}: {
  /** Show ⌘/⌥ (true) or Ctrl/Alt (false); undefined asks the browser. */ mac?: boolean;
}) {
  const t = useTranslations("download");
  const openSettings = useOpenSettings();
  return (
    <section aria-labelledby="desktop-features" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="desktop-features" className="font-semibold text-lg">
          {t("features.title")}
        </h2>
        <Button variant="outline" size="sm" onClick={() => openSettings("hotkeys")}>
          <Keyboard data-icon="inline-start" />
          {t("features.customize")}
        </Button>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map(({ id, icon: Icon }) => (
          <li key={id} className="flex flex-col gap-3 rounded-xl border bg-card p-4">
            <span className="flex size-9 items-center justify-center rounded-lg bg-muted">
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <div className="flex flex-col gap-1">
              <h3 className="font-medium text-sm">{t(`features.${id}.title`)}</h3>
              <p className="text-muted-foreground text-sm">{t(`features.${id}.text`)}</p>
            </div>
            <div className="mt-auto pt-1">
              <Shortcut id={id} mac={mac} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
