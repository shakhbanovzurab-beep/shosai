import { toast } from "sonner";
import { create } from "zustand";

import type { NoteTemplate } from "../domain/templates";
import type { TemplateWords } from "./words";

type TemplatesStore = { created: NoteTemplate[] };

// Templates the user made in this session, newest first; the UI shows them before the samples, which it words
// in the interface language. Local until templates have an API.
const useTemplatesStore = create<TemplatesStore>(() => ({ created: [] }));

export const useCreatedTemplates = () => useTemplatesStore((state) => state.created);

let templateCounter = 0;

export function addTemplate(input: Omit<NoteTemplate, "id">, t: TemplateWords): NoteTemplate {
  templateCounter += 1;
  const template = { ...input, id: `template-${Date.now().toString(36)}-${templateCounter}` };
  useTemplatesStore.setState((state) => ({ created: [template, ...state.created] }));
  toast.success(t("created", { template: template.name }));
  return template;
}
