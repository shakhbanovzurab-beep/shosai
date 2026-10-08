"use client";

import { Building2, FileStack, PlugZap } from "lucide-react";
import { useTranslations } from "use-intl";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspaces } from "@/features/workspace/model/resources";
import { WorkspaceKnowledgeForLeo } from "@/features/workspace/ui/personal/workspace-knowledge-for-leo";

import { FilesTab } from "./files-tab";
import { SourcesTab } from "./sources-tab";

export type KnowledgeBaseTab = "files" | "sources" | "workspaces";

/** Files from File Manager, sources that sync on their own, and what workspaces share. Mirrored in `?tab=`. */
export function KnowledgeBaseTabs({ initialTab }: { initialTab: KnowledgeBaseTab }) {
  const t = useTranslations("knowledgeBase");
  const workspaces = useWorkspaces();
  const inWorkspaces = workspaces.status === "ready" && workspaces.data.workspaces.length > 0;
  return (
    <Tabs
      defaultValue={initialTab}
      onValueChange={(value) => {
        const url = new URL(window.location.href);
        if (value === "files") url.searchParams.delete("tab");
        else url.searchParams.set("tab", value);
        window.history.replaceState(null, "", url);
      }}
      className="gap-6"
    >
      <TabsList variant="line" className="w-full justify-start overflow-x-auto border-b">
        <TabsTrigger value="files" className="flex-none gap-2">
          <FileStack />
          {t("tabs.files")}
        </TabsTrigger>
        <TabsTrigger value="sources" className="flex-none gap-2">
          <PlugZap />
          {t("tabs.sources")}
        </TabsTrigger>
        {inWorkspaces || initialTab === "workspaces" ? (
          <TabsTrigger value="workspaces" className="flex-none gap-2">
            <Building2 />
            {t("tabs.workspaces")}
          </TabsTrigger>
        ) : null}
      </TabsList>
      <TabsContent value="files">
        <FilesTab />
      </TabsContent>
      <TabsContent value="sources">
        <SourcesTab />
      </TabsContent>
      <TabsContent value="workspaces">
        <WorkspaceKnowledgeForLeo />
      </TabsContent>
    </Tabs>
  );
}
