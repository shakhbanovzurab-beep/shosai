import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { type TemplateOut, templatesApi } from "../api/templates-api";
import { SAMPLE_TEMPLATES, type SampleHeading, type SampleTemplateId } from "../data/note-templates";
import type { EnhancedSectionKind, NoteTemplate } from "../domain/templates";
import type { WriteUpKind } from "../domain/write-up";
import { describeNoteError } from "./problem-words";
import type { NotesWords, TemplateWords } from "./words";

type ServerKind = WriteUpKind;

/** Виды разделов сервера и кабинета — одни и те же, в разном написании. */
const TO_CLIENT: Record<ServerKind, EnhancedSectionKind> = {
  summary: "summary",
  key_points: "keyPoints",
  decisions: "decisions",
  action_items: "actionItems",
};
const TO_SERVER: Record<EnhancedSectionKind, ServerKind> = {
  summary: "summary",
  keyPoints: "key_points",
  decisions: "decisions",
  actionItems: "action_items",
};

export const clientKind = (kind: ServerKind) => TO_CLIENT[kind];

/**
 * Заголовок раздела на языке человека: код заголовка встроенного шаблона, код вида у раскладки Leo (её коды —
 * сами виды) или обычное название вида.
 */
export function headingOf(code: string | null, kind: ServerKind, t: TemplateWords) {
  return code !== null && isHeading(code) ? t(`headings.${code}`) : t(`sections.${clientKind(kind)}`);
}

const SHIPPED: ReadonlySet<string> = new Set(SAMPLE_TEMPLATES.map((template) => template.id));
const HEADINGS: ReadonlySet<string> = new Set(
  SAMPLE_TEMPLATES.flatMap((template) => template.sections.map(([, heading]) => heading)),
);
const isShipped = (id: string): id is SampleTemplateId => SHIPPED.has(id);
const isHeading = (code: string): code is SampleHeading => HEADINGS.has(code);

// Шаблоны делят все страницы встреч: новый шаблон сразу виден в меню любой встречи.
const templatesResource = createPollingResource(async () => (await templatesApi.list()).items);

export const useTemplateList = () => usePollingResource(templatesResource);

/**
 * Шаблон из ответа сервера на языке человека: встроенный — по коду и кодам заголовков из каталога кабинета,
 * свой — как его назвал человек.
 */
export function templateOf(out: TemplateOut, t: TemplateWords): NoteTemplate {
  const id = out.id;
  if (!out.builtin || !isShipped(id))
    return {
      id: out.id,
      name: out.name ?? "",
      icon: out.icon as NoteTemplate["icon"],
      description: out.description ?? "",
      sections: out.sections.map((s) => ({
        kind: clientKind(s.kind),
        title: s.title ?? headingOf(s.heading_code, s.kind, t),
      })),
    };
  return {
    id: out.id,
    name: t(`samples.${id}.name`),
    icon: out.icon as NoteTemplate["icon"],
    description: t(`samples.${id}.description`),
    sections: out.sections.map((s) => ({
      kind: clientKind(s.kind),
      title: headingOf(s.heading_code, s.kind, t),
    })),
  };
}

/** Сохраняет новый шаблон человека; null, если сервер отказал (причина — в тосте). */
export async function createTemplate(
  input: Omit<NoteTemplate, "id">,
  words: { t: TemplateWords; notes: NotesWords },
): Promise<TemplateOut | null> {
  try {
    const created = await templatesApi.create({
      name: input.name,
      description: input.description || null,
      icon: input.icon === "enhanced" ? "lightbulb" : input.icon,
      sections: input.sections.map((section) => ({ kind: TO_SERVER[section.kind], title: section.title })),
    });
    templatesResource.update((templates) => [...templates, created]);
    toast.success(words.t("created", { template: input.name }));
    return created;
  } catch (error) {
    toast.error(describeNoteError(error, words.notes));
    return null;
  }
}
