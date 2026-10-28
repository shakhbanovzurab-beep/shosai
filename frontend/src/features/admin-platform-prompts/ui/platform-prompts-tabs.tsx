"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { FeaturesSection } from "./features-section";
import { SafetySection } from "./safety-section";
import { SystemPromptSection } from "./system-prompt-section";
import { VersionsSection } from "./versions-section";

const TABS = [
  { id: "system", label: "Системный промт", panel: SystemPromptSection },
  { id: "safety", label: "Безопасность", panel: SafetySection },
  { id: "features", label: "Функции", panel: FeaturesSection },
  { id: "versions", label: "Версии", panel: VersionsSection },
] as const;

/** Части конфигурации платформы и история; все вкладки правят один черновик, который сохраняется сам. */
export function PlatformPromptsTabs() {
  const {
    state: { revision, published },
  } = usePlatformPrompts();

  return (
    <Tabs defaultValue="system" className="flex flex-col gap-4">
      <div className="overflow-x-auto">
        <TabsList variant="line" className="w-full min-w-max justify-start border-b">
          {TABS.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="flex-none px-3">
              {tab.label}
              {tab.id === "versions" ? (
                <span className="text-muted-foreground text-xs tabular-nums">{published?.number ?? 0}</span>
              ) : null}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      {TABS.map(({ id, panel: Panel }) => (
        <TabsContent key={id} value={id}>
          {/* Новая ревизия (публикация, откат) пересоздаёт панель, чтобы поля со своим текстом начались заново. */}
          <Panel key={revision} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
