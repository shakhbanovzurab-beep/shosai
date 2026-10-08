"use client";

import * as React from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { ENHANCED_TEMPLATE_ID, type NoteTemplate } from "../domain/templates";

/** How long a rewrite "takes" until the backend writes enhanced notes per template. */
const REWRITE_MS = 1200;

/** The template a meeting's enhanced notes follow, and rewriting them with another one or again. */
export function useEnhancedNotes() {
  const t = useTranslations("notesTemplates");
  const [templateId, setTemplateId] = React.useState(ENHANCED_TEMPLATE_ID);
  const [generating, setGenerating] = React.useState(false);
  const timer = React.useRef<number | undefined>(undefined);

  React.useEffect(() => () => window.clearTimeout(timer.current), []);

  const rewrite = (nextId: string, message: string) => {
    window.clearTimeout(timer.current);
    setTemplateId(nextId);
    setGenerating(true);
    timer.current = window.setTimeout(() => {
      setGenerating(false);
      toast.success(message);
    }, REWRITE_MS);
  };

  return {
    templateId,
    generating,
    apply: (template: NoteTemplate) => {
      if (template.id !== templateId) rewrite(template.id, t("rewritten", { template: template.name }));
    },
    regenerate: () => rewrite(templateId, t("regenerated")),
  };
}
