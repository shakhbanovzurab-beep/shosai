"use client";

import { useEffect } from "react";

import { useLocale } from "next-intl";

import type { LanguageCode } from "@/lib/language";

/**
 * The root layout, which sets `<html lang dir>` and the messages, is not re-rendered by client-side
 * navigation. A panel renders this with the language its own request resolved; when a move between panels
 * (the user panel in any language, the admin panel in Russian) lands on another language, the page reloads
 * so every part of it agrees. Switching the language refreshes the root too, so it never reloads then.
 */
export function LocaleGuard({ locale }: { readonly locale: LanguageCode }) {
  const current = useLocale();

  useEffect(() => {
    if (current !== locale) window.location.reload();
  }, [current, locale]);

  return null;
}
