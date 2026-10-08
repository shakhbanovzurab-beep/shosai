import type { useTranslations } from "use-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("kanban")` and so on).
 */

export type KanbanWords = ReturnType<typeof useTranslations<"kanban">>;
export type BoardWords = ReturnType<typeof useTranslations<"kanbanBoards">>;
export type CommonWords = ReturnType<typeof useTranslations<"common">>;
