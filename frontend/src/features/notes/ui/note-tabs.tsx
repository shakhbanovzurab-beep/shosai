"use client";

import { type ReactNode, useState } from "react";

import { Network, NotebookText, ScrollText } from "lucide-react";
import { useTranslations } from "use-intl";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import type { MeetingPage } from "../domain/meeting-page";
import { ENHANCED_TEMPLATE_ID, type NoteTemplate } from "../domain/templates";
import { rewriteNotes, useRewriting, useWriteUp } from "../model/write-up";
import { EnhancedNotes } from "./enhanced-notes";
import { EnhancedNotesIcon } from "./enhanced-notes-icon";
import { EnhancedTab } from "./enhanced-tab";
import { NewTemplateDialog } from "./new-template-dialog";
import { TemplateMenu } from "./template-menu";
import { useTemplates } from "./use-templates";

export type NoteTab = "notes" | "enhanced" | "transcript" | "mind-map";

interface NoteTabsProps {
  readonly note: MeetingPage;
  readonly defaultTab: NoteTab;
  /** Свои заметки человека. */
  readonly notes: ReactNode;
  /** Оборачивает задачи встречи, например чтобы показать их задачами рабочего пространства. */
  readonly renderActionItems?: (local: ReactNode) => ReactNode;
  readonly transcript: ReactNode;
  readonly mindMap: ReactNode;
}

/** Вкладки встречи: свои заметки, запись Leo (с меню шаблонов на вкладке), расшифровка и интеллект-карта. */
export function NoteTabs({ note, defaultTab, notes, renderActionItems, transcript, mindMap }: NoteTabsProps) {
  const t = useTranslations("notesNote");
  const templateWords = useTranslations("notesTemplates");
  const notesWords = useTranslations("notes");
  // Вкладка, на которую человек перешёл; до того — исходная.
  const [picked, setPicked] = useState<NoteTab | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const templates = useTemplates();
  const writeUp = useWriteUp(note.id);
  const rewriting = useRewriting(note.id);
  const written = writeUp.status === "ready" ? writeUp.data : null;
  const template = templates.find(written?.templateId ?? note.templateId ?? ENHANCED_TEMPLATE_ID);
  // Переписать запись может тот, кто может менять встречу, и только когда она уже написана.
  const canRewrite = note.manageable && written !== null;
  const words = { t: templateWords, notes: notesWords };

  const fromMenu = (action: () => void) => {
    setMenuOpen(false);
    action();
  };
  const apply = (next: NoteTemplate) => {
    if (next.id !== template.id) void rewriteNotes(note.id, next, words, false);
  };

  return (
    <>
      <Tabs defaultValue={defaultTab} onValueChange={(value) => setPicked(value as NoteTab)} className="gap-6">
        <TabsList variant="line" className="w-full justify-start border-b">
          <TabsTrigger value="notes" className="flex-none">
            <NotebookText />
            {t("tabs.notes")}
          </TabsTrigger>
          {canRewrite ? (
            <EnhancedTab active={(picked ?? defaultTab) === "enhanced"} open={menuOpen} onOpenChange={setMenuOpen}>
              <TemplateMenu
                enhanced={templates.enhanced}
                templates={templates.templates}
                value={template}
                generating={rewriting}
                onPick={(next) => fromMenu(() => apply(next))}
                onRegenerate={() => fromMenu(() => void rewriteNotes(note.id, template, words, true))}
                onNewTemplate={() => fromMenu(() => setCreating(true))}
              />
            </EnhancedTab>
          ) : (
            <TabsTrigger value="enhanced" className="flex-none">
              <EnhancedNotesIcon />
              {t("tabs.enhanced")}
            </TabsTrigger>
          )}
          <TabsTrigger value="transcript" className="flex-none">
            <ScrollText />
            {t("tabs.transcript")}
          </TabsTrigger>
          <TabsTrigger value="mind-map" className="flex-none">
            <Network />
            {t("tabs.mindMap")}
          </TabsTrigger>
        </TabsList>
        {/* Заметки и запись Leo остаются смонтированными: несохранённая правка переживает взгляд на другую вкладку. */}
        <TabsContent value="notes" forceMount className="data-[state=inactive]:hidden">
          {notes}
        </TabsContent>
        <TabsContent value="enhanced" forceMount className="flex flex-col gap-6 data-[state=inactive]:hidden">
          <EnhancedNotes note={note} template={template} renderActionItems={renderActionItems} />
          {written ? (
            <p className="text-muted-foreground text-xs">
              {template.id === ENHANCED_TEMPLATE_ID
                ? t("enhanced.writtenBy")
                : t("enhanced.writtenByTemplate", { template: template.name })}
            </p>
          ) : null}
        </TabsContent>
        <TabsContent value="transcript">{transcript}</TabsContent>
        <TabsContent value="mind-map">{mindMap}</TabsContent>
      </Tabs>
      <NewTemplateDialog open={creating} onOpenChange={setCreating} onCreated={apply} />
    </>
  );
}
