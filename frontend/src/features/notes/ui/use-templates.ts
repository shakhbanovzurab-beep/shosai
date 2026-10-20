"use client";

import { useTranslations } from "use-intl";

import { ENHANCED_TEMPLATE_ID, type NoteTemplate } from "../domain/templates";
import { templateOf, useTemplateList } from "../model/templates";
import { enhancedTemplate } from "./template-words";

/**
 * Раскладка Leo и шаблоны для выбора (сначала свои, затем встроенные) на языке человека, с сервера; `find`
 * возвращает раскладку Leo для неизвестного id. Пока список едет, в меню только раскладка Leo.
 */
export function useTemplates() {
  const t = useTranslations("notesTemplates");
  const list = useTemplateList();
  const enhanced = enhancedTemplate(t);
  const loaded = list.status === "ready" ? list.data : [];
  const own: NoteTemplate[] = [];
  const shipped: NoteTemplate[] = [];
  for (const out of loaded) {
    if (out.id === ENHANCED_TEMPLATE_ID) continue;
    (out.builtin ? shipped : own).push(templateOf(out, t));
  }
  const templates = [...own, ...shipped];
  const find = (id: string) => templates.find((template) => template.id === id) ?? enhanced;
  return { enhanced, templates, find };
}
