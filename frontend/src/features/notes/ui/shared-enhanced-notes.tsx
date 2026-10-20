import type * as React from "react";

import type { LucideIcon } from "lucide-react";
import { Gavel, Lightbulb, ListChecks } from "lucide-react";
import { useTranslations } from "use-intl";

import type { EnhancedSectionKind, NoteTemplate } from "../domain/templates";
import { NotesWriting } from "./notes-writing";

/** Что Leo написал о встрече, как его показывает публичная страница ссылки (до шага 19 плана notes). */
export interface EnhancedContent {
  readonly summary: string;
  readonly keyPoints: string[];
  readonly decisions: string[];
  readonly actionItems: React.ReactNode | null;
}

const SECTION_ICONS: Record<Exclude<EnhancedSectionKind, "summary">, LucideIcon> = {
  keyPoints: Lightbulb,
  decisions: Gavel,
  actionItems: ListChecks,
};

function hasContent(kind: EnhancedSectionKind, content: EnhancedContent) {
  if (kind === "summary") return content.summary.length > 0;
  if (kind === "actionItems") return content.actionItems !== null;
  return content[kind].length > 0;
}

interface SharedEnhancedNotesProps {
  readonly template: NoteTemplate;
  readonly generating: boolean;
  readonly content: EnhancedContent;
}

/** Запись Leo на публичной странице ссылки, разложенная по шаблону. Написанное Leo сохраняет своё направление. */
export function SharedEnhancedNotes({ template, generating, content }: SharedEnhancedNotesProps) {
  const t = useTranslations("notesNote");
  if (generating) return <NotesWriting />;

  const sections = template.sections.filter((section) => hasContent(section.kind, content));
  if (sections.length === 0)
    return <p className="text-muted-foreground text-sm">{t("enhanced.nothingFor", { template: template.name })}</p>;

  return (
    <div className="flex flex-col gap-8">
      {sections.map(({ kind, title }) => {
        if (kind === "summary")
          return (
            <section key={kind} className="flex flex-col gap-2" aria-labelledby="enhanced-summary-heading">
              <h3
                id="enhanced-summary-heading"
                className="font-medium text-muted-foreground text-xs uppercase tracking-wide"
              >
                {title}
              </h3>
              <p dir="auto" className="text-sm leading-relaxed">
                {content.summary}
              </p>
            </section>
          );
        return (
          <NoteSection key={kind} icon={SECTION_ICONS[kind]} title={title}>
            {kind === "keyPoints" ? (
              <ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm marker:text-muted-foreground">
                {content.keyPoints.map((point) => (
                  <li key={point} dir="auto">
                    {point}
                  </li>
                ))}
              </ul>
            ) : null}
            {kind === "decisions" ? (
              <ul className="flex flex-col gap-1.5 text-sm">
                {content.decisions.map((decision) => (
                  <li key={decision} dir="auto" className="rounded-lg border bg-card px-3 py-2">
                    {decision}
                  </li>
                ))}
              </ul>
            ) : null}
            {kind === "actionItems" ? content.actionItems : null}
          </NoteSection>
        );
      })}
    </div>
  );
}

interface NoteSectionProps {
  readonly icon: LucideIcon;
  readonly title: string;
  readonly children: React.ReactNode;
}

function NoteSection({ icon: Icon, title, children }: NoteSectionProps) {
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
