"use client";

import { useMemo } from "react";

import { useLocale, useTranslations } from "use-intl";

import { formatBytes } from "@/i18n/format-units";

/*
 * The words the model's actions put in their toasts. Actions are plain functions, so the Client Component
 * that calls one passes them in: `const words = useFileActionWords()`, then `setFileLeo(file, true, words)`.
 */

export type FileActionWords = {
  t: ReturnType<typeof useTranslations<"fileManagerActions">>;
  common: ReturnType<typeof useTranslations<"common">>;
  /** "1.2 GB" in the user's language. */
  bytes: (value: number) => string;
};

export function useFileActionWords(): FileActionWords {
  const t = useTranslations("fileManagerActions");
  const common = useTranslations("common");
  const locale = useLocale();
  return useMemo(() => ({ t, common, bytes: (value: number) => formatBytes(locale, value) }), [t, common, locale]);
}
