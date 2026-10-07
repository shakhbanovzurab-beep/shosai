/** The parts of a meeting Leo writes up from the transcript and the user's own notes. */
export type EnhancedSectionKind = "summary" | "keyPoints" | "decisions" | "actionItems";

/** In Leo's own order; the UI names each kind in the interface language. */
export const SECTION_KINDS: EnhancedSectionKind[] = ["summary", "keyPoints", "decisions", "actionItems"];

/** The icons a template can have, like a board's; "enhanced" is kept for Leo's own layout. */
export const TEMPLATE_ICONS = [
  "briefcase",
  "chart",
  "handshake",
  "landmark",
  "lightbulb",
  "magnet",
  "phone",
  "rocket",
  "calendar",
  "users",
] as const;

export type TemplateIcon = (typeof TEMPLATE_ICONS)[number] | "enhanced";

export interface TemplateSection {
  kind: EnhancedSectionKind;
  title: string;
}

/**
 * A template the product ships, as codes: its name, description and section headings come from the
 * interface language's catalog, by `id` and by heading code.
 */
export interface SampleTemplate {
  readonly id: string;
  readonly icon: TemplateIcon;
  readonly sections: readonly (readonly [kind: EnhancedSectionKind, heading: string])[];
}

/** How enhanced notes are laid out: which sections, in what order and under which headings, in words. */
export interface NoteTemplate {
  id: string;
  name: string;
  icon: TemplateIcon;
  description: string;
  sections: TemplateSection[];
}

/** Leo's own layout, used until the user picks a template: every section, in `SECTION_KINDS` order. */
export const ENHANCED_TEMPLATE_ID = "enhanced";

/** Templates whose name or description contains the query, ignoring case. */
export function filterTemplates(templates: NoteTemplate[], query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return templates;
  return templates.filter(
    (template) => template.name.toLowerCase().includes(needle) || template.description.toLowerCase().includes(needle),
  );
}
