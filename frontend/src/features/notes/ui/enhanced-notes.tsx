"use client";

import type * as React from "react";

import type { LucideIcon } from "lucide-react";
import { Gavel, Lightbulb, ListChecks } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";

import type { NotesState } from "../domain/library";
import type { NoteTemplate } from "../domain/templates";
import type { WriteUpFinding, WriteUpKind, WriteUpSection } from "../domain/write-up";
import { headingOf } from "../model/templates";
import { retryWriteUp, useRewriting, useWriteUp } from "../model/write-up";
import { ActionItems } from "./action-items";
import { NotesWriting } from "./notes-writing";

const SECTION_ICONS: Record<Exclude<WriteUpKind, "summary">, LucideIcon> = {
  key_points: Lightbulb,
  decisions: Gavel,
  action_items: ListChecks,
};

const hasContent = (section: WriteUpSection) =>
  section.kind === "summary" ? Boolean(section.text) : (section.items?.length ?? 0) > 0;

interface EnhancedNotesProps {
  readonly note: { readonly id: string; readonly notes: NotesState };
  readonly template: NoteTemplate;
  /** Оборачивает задачи встречи, например чтобы показать их задачами рабочего пространства. */
  readonly renderActionItems?: (local: React.ReactNode) => React.ReactNode;
}

/** Запись Leo о встрече, разложенная сервером по шаблону. Написанное Leo сохраняет своё направление текста. */
export function EnhancedNotes({ note, template, renderActionItems }: EnhancedNotesProps) {
  const t = useTranslations("notesNote");
  const words = useTranslations("notesTemplates");
  const writeUp = useWriteUp(note.id);
  const rewriting = useRewriting(note.id);
  if (rewriting || writeUp.status === "loading") return <NotesWriting />;
  if (writeUp.status === "error")
    return (
      <LoadError
        title={t("enhanced.loadFailed")}
        message={writeUp.message}
        onRetry={() => void retryWriteUp(note.id)}
      />
    );
  if (writeUp.data === null) {
    if (note.notes === "processing") return <NotesWriting />;
    return (
      <p className="text-muted-foreground text-sm">
        {note.notes === "failed" ? t("enhanced.failed") : t("enhanced.none")}
      </p>
    );
  }
  const sections = writeUp.data.sections.filter(hasContent);
  if (sections.length === 0)
    return <p className="text-muted-foreground text-sm">{t("enhanced.nothingFor", { template: template.name })}</p>;

  return (
    <div className="flex flex-col gap-8">
      {sections.map((section) => {
        const title = section.title ?? headingOf(section.headingCode, section.kind, words);
        if (section.kind === "summary")
          return (
            <section key={section.kind} className="flex flex-col gap-2" aria-label={title}>
              <h3 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">{title}</h3>
              <p dir="auto" className="text-sm leading-relaxed">
                {section.text}
              </p>
            </section>
          );
        const items = section.items ?? [];
        const actionItems = <ActionItems items={items} />;
        return (
          <NoteSection key={section.kind} icon={SECTION_ICONS[section.kind]} title={title}>
            {section.kind === "action_items" ? (
              (renderActionItems?.(actionItems) ?? actionItems)
            ) : (
              <Points kind={section.kind} items={items} />
            )}
          </NoteSection>
        );
      })}
    </div>
  );
}

function Points({ kind, items }: { readonly kind: WriteUpKind; readonly items: readonly WriteUpFinding[] }) {
  if (kind === "decisions")
    return (
      <ul className="flex flex-col gap-1.5 text-sm">
        {items.map((item) => (
          <li key={item.id} dir="auto" className="rounded-lg border bg-card px-3 py-2">
            {item.text}
          </li>
        ))}
      </ul>
    );
  return (
    <ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm marker:text-muted-foreground">
      {items.map((item) => (
        <li key={item.id} dir="auto">
          {item.text}
        </li>
      ))}
    </ul>
  );
}

function NoteSection({
  icon: Icon,
  title,
  children,
}: {
  readonly icon: LucideIcon;
  readonly title: string;
  readonly children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="flex items-center gap-2 font-medium text-sm">
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        {title}
      </h3>
      {children}
    </section>
  );
}
