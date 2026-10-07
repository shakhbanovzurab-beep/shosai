import type { useTranslations } from "next-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("knowledgeBaseSources")` and so on).
 */

export type KnowledgeWords = ReturnType<typeof useTranslations<"knowledgeBase">>;
export type SourceWords = ReturnType<typeof useTranslations<"knowledgeBaseSources">>;
