"use client";

import { cn } from "cn";
import { Blocks, Brain, CircleUser, CreditCard, Gauge, Keyboard, type LucideIcon, Plug, Shield } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { useMe } from "@/features/identity/model/session-store";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { SettingsSection } from "../domain/sections";
import { useSettingsDialog } from "../model/dialog-store";
import { leoSettingsResource } from "../model/leo-settings";
import { settingsResource } from "../model/settings-resources";
import { AccountSection } from "./account/account-section";
import { BillingSection } from "./billing/billing-section";
import { ConnectorsSection } from "./connectors/connectors-section";
import { HotkeysSection } from "./hotkeys/hotkeys-section";
import { LeoSection } from "./leo/leo-section";
import { McpSection } from "./mcp/mcp-section";
import { MemorySection } from "./memory/memory-section";
import { PrivacySection } from "./privacy/privacy-section";
import { SectionState } from "./section-state";
import { UsageSection } from "./usage/usage-section";

/** Leo is shown as its orb, like everywhere else in the app; the rest use plain icons. */
const LeoOrb = () => (
  <span className="-m-0.5 flex size-5 shrink-0 [&_canvas]:size-5!" aria-hidden="true">
    <ThinkingOrb state="breathing" size={20} />
  </span>
);

/** The sections in the order the navigation lists them; their names come from the catalog. */
const SECTIONS: { id: SettingsSection; icon: LucideIcon | null }[] = [
  { id: "account", icon: CircleUser },
  { id: "privacy", icon: Shield },
  { id: "billing", icon: CreditCard },
  { id: "usage", icon: Gauge },
  { id: "leo", icon: null },
  { id: "mcp", icon: Plug },
  { id: "memory", icon: Brain },
  { id: "connectors", icon: Blocks },
  { id: "hotkeys", icon: Keyboard },
];

/**
 * Account и Privacy — данные identity, уже загруженные с сессией; разделы на предпочтениях ждут их, остальные
 * загружают своё сами.
 */
function SectionBody({ section }: { section: SettingsSection }) {
  const settings = usePollingResource(settingsResource);
  const me = useMe();
  if (section === "account" || section === "privacy") {
    if (me === null) return <Spinner className="mx-auto my-10" />;
    return section === "account" ? <AccountSection me={me} /> : <PrivacySection me={me} />;
  }
  if (section === "billing") return <BillingSection />;
  if (section === "usage") return <UsageSection />;
  if (section === "mcp") return <McpSection />;
  if (section === "connectors") return <ConnectorsSection />;
  if (section === "leo") return <LeoSettingsBody />;
  return (
    <SectionState state={settings} onRetry={() => void settingsResource.refresh()}>
      {(data) => {
        if (section === "hotkeys") return <HotkeysSection settings={data} />;
        return <MemorySection settings={data} />;
      }}
    </SectionState>
  );
}

/** Settings › Leo, read from agent's own route. */
function LeoSettingsBody() {
  const settings = usePollingResource(leoSettingsResource);
  return (
    <SectionState state={settings} onRetry={() => void leoSettingsResource.refresh()}>
      {(data) => <LeoSection settings={data} />}
    </SectionState>
  );
}

/** Settings in one dialog, like Claude's: sections at the start, the chosen one beside them. Changes save at once. */
export function SettingsDialog() {
  const t = useTranslations("settings");
  const { section, open, close } = useSettingsDialog();
  const current = SECTIONS.find((s) => s.id === section) ?? SECTIONS[0];

  return (
    <Dialog open={section !== null} onOpenChange={(next) => (next ? undefined : close())}>
      <DialogContent className="flex h-[min(44rem,88dvh)] flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl md:flex-row">
        <nav
          aria-label={t("dialog.sectionsLabel")}
          className="flex shrink-0 gap-1 overflow-x-auto border-b bg-muted/40 p-2 md:w-52 md:flex-col md:border-e md:border-b-0 md:p-3"
        >
          <DialogTitle className="hidden px-2 pt-1 pb-3 font-medium text-lg md:block">{t("dialog.title")}</DialogTitle>
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={item.id === current.id ? "page" : undefined}
              onClick={() => open(item.id)}
              className={cn(
                "flex shrink-0 cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-start text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                item.id === current.id
                  ? "bg-background font-medium text-foreground shadow-xs"
                  : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
              )}
            >
              {item.icon ? <item.icon className="size-4 shrink-0" aria-hidden="true" /> : <LeoOrb />}
              {t(`sections.${item.id}`)}
            </button>
          ))}
        </nav>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="border-b px-6 py-4 pe-12">
            <h2 className="font-medium text-lg">{t(`sections.${current.id}`)}</h2>
            <DialogDescription className="sr-only">{t("dialog.autosave")}</DialogDescription>
          </div>
          <div data-settings-scroll className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            <SectionBody key={current.id} section={current.id} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
