"use client";

import { useOptimistic, useTransition } from "react";

import { useRouter } from "next/navigation";

import { setClientCookie } from "@/lib/cookie.client";
import { isLanguageCode, LANGUAGE_COOKIE, type LanguageCode } from "@/lib/language";

import { useUiLanguage } from "./use-ui-language";

const YEAR_DAYS = 365;

/**
 * The interface language and a way to switch it. The choice is a cookie the server reads, so refreshing the
 * route re-renders the page in the new language in place, without a reload. Meanwhile `language` already
 * shows the new choice, so a picker's tick moves at once.
 */
export function useSwitchLanguage() {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [language, showLanguage] = useOptimistic<LanguageCode>(useUiLanguage());

  const switchLanguage = (code: string) => {
    if (!isLanguageCode(code)) return;
    setClientCookie(LANGUAGE_COOKIE, code, YEAR_DAYS);
    startTransition(() => {
      showLanguage(code);
      router.refresh();
    });
  };

  return { language, switchLanguage };
}
