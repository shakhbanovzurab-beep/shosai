import { SAMPLE_TEMPLATES } from "../data/note-templates";
import { ENHANCED_TEMPLATE_ID, type NoteTemplate, SECTION_KINDS } from "../domain/templates";
import type { TemplateWords } from "../model/words";

/** Leo's own layout in the interface language: every section, under its usual heading. */
export const enhancedTemplate = (t: TemplateWords): NoteTemplate => ({
  id: ENHANCED_TEMPLATE_ID,
  name: t("enhanced.name"),
  icon: "enhanced",
  description: t("enhanced.description"),
  sections: SECTION_KINDS.map((kind) => ({ kind, title: t(`sections.${kind}`) })),
});

/** The templates the product ships, worded in the interface language. */
export const sampleTemplates = (t: TemplateWords): NoteTemplate[] =>
  SAMPLE_TEMPLATES.map((sample) => ({
    id: sample.id,
    name: t(`samples.${sample.id}.name`),
    icon: sample.icon,
    description: t(`samples.${sample.id}.description`),
    sections: sample.sections.map(([kind, heading]) => ({ kind, title: t(`headings.${heading}`) })),
  }));
