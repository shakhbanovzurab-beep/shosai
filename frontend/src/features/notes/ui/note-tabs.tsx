"use client";

import { type ReactNode, useState } from "react";

import { Network, NotebookText, ScrollText } from "lucide-react";
import { useTranslations } from "next-intl";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ENHANCED_TEMPLATE_ID } from "../domain/templates";
import { useEnhancedNotes } from "../model/use-enhanced-notes";
import { type EnhancedContent, EnhancedNotes } from "./enhanced-notes";
import { EnhancedTab } from "./enhanced-tab";
import { NewTemplateDialog } from "./new-template-dialog";
import { TemplateMenu } from "./template-menu";
import { useTemplates } from "./use-templates";

export type NoteTab = "notes" | "enhanced" | "transcript" | "mind-map";

interface NoteTabsProps {
  readonly defaultTab: NoteTab;
  /** The user's own notes. */
  readonly notes: ReactNode;
  /** What Leo wrote, laid out here by the template picked in the Enhanced tab. */
  readonly enhanced: EnhancedContent;
  readonly transcript: ReactNode;
  readonly mindMap: ReactNode;
}

/** A note's tabs: Notes, Enhanced (whose tab holds the template menu), Transcript and Mind map. */
export function NoteTabs({ defaultTab, notes, enhanced, transcript, mindMap }: NoteTabsProps) {
  const t = useTranslations("notesNote");
  // The tab the user switched to; the default until they do.
  const [picked, setPicked] = useState<NoteTab | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const templates = useTemplates();
  const enhancedNotes = useEnhancedNotes();
  const template = templates.find(enhancedNotes.templateId);

  const fromMenu = (action: () => void) => {
    setMenuOpen(false);
    action();
  };

  return (
    <>
      <Tabs defaultValue={defaultTab} onValueChange={(value) => setPicked(value as NoteTab)} className="gap-6">
        <TabsList variant="line" className="w-full justify-start border-b">
          <TabsTrigger value="notes" className="flex-none">
            <NotebookText />
            {t("tabs.notes")}
          </TabsTrigger>
          <EnhancedTab active={(picked ?? defaultTab) === "enhanced"} open={menuOpen} onOpenChange={setMenuOpen}>
            <TemplateMenu
              enhanced={templates.enhanced}
              templates={templates.templates}
              value={template}
              generating={enhancedNotes.generating}
              onPick={(next) => fromMenu(() => enhancedNotes.apply(next))}
              onRegenerate={() => fromMenu(enhancedNotes.regenerate)}
              onNewTemplate={() => fromMenu(() => setCreating(true))}
            />
          </EnhancedTab>
          <TabsTrigger value="transcript" className="flex-none">
            <ScrollText />
            {t("tabs.transcript")}
          </TabsTrigger>
          <TabsTrigger value="mind-map" className="flex-none">
            <Network />
            {t("tabs.mindMap")}
          </TabsTrigger>
        </TabsList>
        {/* Notes and Enhanced stay mounted: an edit still waiting to save, the chosen template and ticked action
            items all survive a look at another tab. */}
        <TabsContent value="notes" forceMount className="data-[state=inactive]:hidden">
          {notes}
        </TabsContent>
        <TabsContent value="enhanced" forceMount className="flex flex-col gap-6 data-[state=inactive]:hidden">
          <EnhancedNotes template={template} generating={enhancedNotes.generating} content={enhanced} />
          <p className="text-muted-foreground text-xs">
            {template.id === ENHANCED_TEMPLATE_ID
              ? t("enhanced.writtenBy")
              : t("enhanced.writtenByTemplate", { template: template.name })}
          </p>
        </TabsContent>
        <TabsContent value="transcript">{transcript}</TabsContent>
        <TabsContent value="mind-map">{mindMap}</TabsContent>
      </Tabs>
      <NewTemplateDialog open={creating} onOpenChange={setCreating} onCreated={enhancedNotes.apply} />
    </>
  );
}
