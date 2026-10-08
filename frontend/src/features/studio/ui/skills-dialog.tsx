"use client";

import { useTranslations } from "use-intl";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { useSkills } from "../model/studio-resources";
import { SkillsMine } from "./skills-mine";
import { SkillsReadyMade } from "./skills-ready-made";
import { SkillsRepository } from "./skills-repository";

/** Find skills on skills.sh or in a GitHub repository, and manage the ones you've installed. */
export function SkillsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useTranslations("studioSkills");
  const state = useSkills();
  const installed = state.status === "ready" ? state.data.skills : [];

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="flex h-[min(36rem,85dvh)] flex-col gap-0 sm:max-w-2xl">
        <DialogHeader className="border-b pb-4">
          <DialogTitle>{t("title")}</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="ready-made" className="min-h-0 flex-1 gap-5 pt-4">
          <TabsList variant="line" className="mx-auto">
            <TabsTrigger value="ready-made">{t("tabs.readyMade")}</TabsTrigger>
            <TabsTrigger value="repository">{t("tabs.repository")}</TabsTrigger>
            <TabsTrigger value="mine">{t("tabs.mine", { count: installed.length })}</TabsTrigger>
          </TabsList>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <TabsContent value="ready-made">
              <SkillsReadyMade installed={installed} />
            </TabsContent>
            <TabsContent value="repository">
              <SkillsRepository installed={installed} />
            </TabsContent>
            <TabsContent value="mine">
              {state.status === "ready" ? <SkillsMine skills={installed} /> : <Skeleton className="h-32 rounded-xl" />}
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
