"use client";

import { useMemo } from "react";

import { useTranslations } from "use-intl";

/*
 * The words the model's actions put in their toasts. Actions are plain functions, so the Client Component
 * that calls one passes them in: `const words = useFileActionWords()`, then `setFileLeo(file, true, words)`.
 */

export type FileActionWords = {
  t: ReturnType<typeof useTranslations<"fileManagerActions">>;
  common: ReturnType<typeof useTranslations<"common">>;
};

export function useFileActionWords(): FileActionWords {
  const t = useTranslations("fileManagerActions");
  const common = useTranslations("common");
  return useMemo(() => ({ t, common }), [t, common]);
}
