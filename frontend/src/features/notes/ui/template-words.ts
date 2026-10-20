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
