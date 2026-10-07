import type { useTranslations } from "next-intl";

/*
 * The catalog the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("pagesSupport")`).
 */

export type SupportWords = ReturnType<typeof useTranslations<"pagesSupport">>;
