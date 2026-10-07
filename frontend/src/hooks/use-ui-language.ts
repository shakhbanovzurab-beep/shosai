"use client";

import { useLocale } from "next-intl";

import type { LanguageCode } from "@/lib/language";

/** The interface language of the current page: the one the user picked in /app, Russian in the admin panel. */
export function useUiLanguage(): LanguageCode {
  return useLocale();
}
