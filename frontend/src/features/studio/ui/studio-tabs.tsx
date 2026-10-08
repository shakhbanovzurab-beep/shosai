"use client";

import { Cpu, FileText, MessageSquareText } from "lucide-react";
import { useTranslations } from "use-intl";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import type { StudioTab } from "../domain/studio-tabs";
import { ContextTab } from "./context-tab";
import { ModelsTab } from "./models-tab";
import { PromptsTab } from "./prompts-tab";

/** Context, Prompts and Models on one page; the open tab is mirrored in `?tab=` so it can be linked to. */
export function StudioTabs({ initialTab }: { initialTab: StudioTab }) {
  const t = useTranslations("studio");
  return (
    <Tabs
      defaultValue={initialTab}
      onValueChange={(value) => {
        const url = new URL(window.location.href);
        if (value === "context") url.searchParams.delete("tab");
        else url.searchParams.set("tab", value);
        window.history.replaceState(null, "", url);
      }}
      className="gap-6"
    >
      <TabsList variant="line" className="w-full justify-start border-b">
        <TabsTrigger value="context" className="flex-none gap-2">
          <FileText />
          {t("tabs.context")}
        </TabsTrigger>
        <TabsTrigger value="prompts" className="flex-none gap-2">
          <MessageSquareText />
          {t("tabs.prompts")}
        </TabsTrigger>
        <TabsTrigger value="models" className="flex-none gap-2">
          <Cpu />
          {t("tabs.models")}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="context">
        <ContextTab />
      </TabsContent>
      <TabsContent value="prompts">
        <PromptsTab />
      </TabsContent>
      <TabsContent value="models">
        <ModelsTab />
      </TabsContent>
    </Tabs>
  );
}
