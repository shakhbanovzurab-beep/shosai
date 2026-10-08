"use client";

import { useTranslations } from "use-intl";

import { useCreatedTemplates } from "../model/templates-store";
import { enhancedTemplate, sampleTemplates } from "./template-words";

/**
 * Leo's own layout and the templates to pick from (the user's own first, then the samples), in the interface
 * language; `find` falls back to Leo's layout for an unknown id.
 */
export function useTemplates() {
  const t = useTranslations("notesTemplates");
  const enhanced = enhancedTemplate(t);
  const templates = [...useCreatedTemplates(), ...sampleTemplates(t)];
  const find = (id: string) => templates.find((template) => template.id === id) ?? enhanced;
  return { enhanced, templates, find };
}
