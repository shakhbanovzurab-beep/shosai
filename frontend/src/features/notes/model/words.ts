import type { useTranslations } from "use-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("notes")` and so on).
 */

export type NotesWords = ReturnType<typeof useTranslations<"notes">>;
export type NoteWords = ReturnType<typeof useTranslations<"notesNote">>;
export type TemplateWords = ReturnType<typeof useTranslations<"notesTemplates">>;
export type ShareWords = ReturnType<typeof useTranslations<"notesShare">>;
export type CommonWords = ReturnType<typeof useTranslations<"common">>;
