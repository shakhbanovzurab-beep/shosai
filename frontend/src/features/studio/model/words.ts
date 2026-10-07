import type { useTranslations } from "next-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("studioPrompts")` and so on).
 */

export type StudioWords = ReturnType<typeof useTranslations<"studio">>;
export type PromptWords = ReturnType<typeof useTranslations<"studioPrompts">>;
export type SkillWords = ReturnType<typeof useTranslations<"studioSkills">>;
