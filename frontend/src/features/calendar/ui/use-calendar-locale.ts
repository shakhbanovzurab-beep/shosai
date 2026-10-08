"use client";

import { use } from "react";

import type { LocaleInput } from "@fullcalendar/react";
import { useLocale } from "use-intl";

import type { LanguageCode } from "@/lib/language";

type Loader = () => Promise<LocaleInput>;

/*
 * FullCalendar's own locale for the interface language: month and day names, the week's first day, and its
 * built-in words ("all-day", "+2 more"). English is built in; the others load on first use.
 */
const LOADERS: Record<Exclude<LanguageCode, "en">, Loader> = {
  fr: () => import("@fullcalendar/react/locales/fr").then((module) => module.default),
  de: () => import("@fullcalendar/react/locales/de").then((module) => module.default),
  ru: () => import("@fullcalendar/react/locales/ru").then((module) => module.default),
  nl: () => import("@fullcalendar/react/locales/nl").then((module) => module.default),
  it: () => import("@fullcalendar/react/locales/it").then((module) => module.default),
  es: () => import("@fullcalendar/react/locales/es").then((module) => module.default),
  "pt-BR": () => import("@fullcalendar/react/locales/pt-br").then((module) => module.default),
  ar: () => import("@fullcalendar/react/locales/ar").then((module) => module.default),
  tr: () => import("@fullcalendar/react/locales/tr").then((module) => module.default),
  ko: () => import("@fullcalendar/react/locales/ko").then((module) => module.default),
  hi: () => import("@fullcalendar/react/locales/hi").then((module) => module.default),
  vi: () => import("@fullcalendar/react/locales/vi").then((module) => module.default),
  "zh-Hant": () => import("@fullcalendar/react/locales/zh-tw").then((module) => module.default),
  ja: () => import("@fullcalendar/react/locales/ja").then((module) => module.default),
  id: () => import("@fullcalendar/react/locales/id").then((module) => module.default),
};

const loaded = new Map<LanguageCode, Promise<LocaleInput>>();

function loadLocale(language: Exclude<LanguageCode, "en">) {
  let locale = loaded.get(language);
  if (!locale) {
    locale = LOADERS[language]();
    loaded.set(language, locale);
  }
  return locale;
}

/**
 * FullCalendar's locale for the interface language, or "en". It suspends while a locale loads the first time,
 * so render the calendar inside a Suspense boundary.
 */
export function useCalendarLocale(): LocaleInput | "en" {
  const language = useLocale();
  return language === "en" ? "en" : use(loadLocale(language));
}
