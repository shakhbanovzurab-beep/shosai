import type { useTranslations } from "use-intl";

/*
 * Каталоги, которыми действия модели называют свои тосты. Действия — обычные функции, поэтому клиентский
 * компонент, который их вызывает, передаёт свой переводчик (`useTranslations("studioPrompts")` и другие).
 */

export type StudioWords = ReturnType<typeof useTranslations<"studio">>;
export type StudioApiWords = ReturnType<typeof useTranslations<"studioApi">>;
export type PromptWords = ReturnType<typeof useTranslations<"studioPrompts">>;
export type SkillWords = ReturnType<typeof useTranslations<"studioSkills">>;
