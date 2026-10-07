"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { BehaviorSection } from "./behavior-section";
import { FeaturesSection } from "./features-section";
import { SafetySection } from "./safety-section";
import { SystemPromptSection } from "./system-prompt-section";
import { VersionsSection } from "./versions-section";

const TABS = [
  { id: "system", label: "Системный промт", panel: SystemPromptSection },
  { id: "behavior", label: "Поведение", panel: BehaviorSection },
  { id: "safety", label: "Безопасность", panel: SafetySection },
  { id: "features", label: "Функции", panel: FeaturesSection },
  { id: "versions", label: "Версии", panel: VersionsSection },
] as const;

/** The five parts of the platform configuration; every tab edits the same autosaved draft. */
export function PlatformPromptsTabs() {
  const {
    state: { revision, versions },
  } = usePlatformPrompts();

  return (
    <Tabs defaultValue="system" className="flex flex-col gap-4">
      <div className="overflow-x-auto">
        <TabsList variant="line" className="w-full min-w-max justify-start border-b">
          {TABS.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="flex-none px-3">
              {tab.label}
              {tab.id === "versions" ? (
                <span className="text-muted-foreground text-xs tabular-nums">{versions.length}</span>
              ) : null}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      {TABS.map(({ id, panel: Panel }) => (
        <TabsContent key={id} value={id}>
          {/* A new revision (publish, rollback) remounts the panel so inputs holding their own text start fresh. */}
          <Panel key={revision} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
