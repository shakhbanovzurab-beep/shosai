"use client";

import { use } from "react";

import type { Locale } from "date-fns";
import { useLocale } from "use-intl";

import type { LanguageCode } from "@/lib/language";

/*
 * date-fns locales for widgets that take one (react-day-picker, FullCalendar's date-fns adapter). Only the
 * interface language's locale is loaded, on first use, and shared by every widget.
 */
const LOADERS: Record<LanguageCode, () => Promise<Locale>> = {
  en: () => import("date-fns/locale/en-US").then((module) => module.enUS),
  fr: () => import("date-fns/locale/fr").then((module) => module.fr),
  de: () => import("date-fns/locale/de").then((module) => module.de),
  ru: () => import("date-fns/locale/ru").then((module) => module.ru),
  nl: () => import("date-fns/locale/nl").then((module) => module.nl),
  it: () => import("date-fns/locale/it").then((module) => module.it),
  es: () => import("date-fns/locale/es").then((module) => module.es),
  "pt-BR": () => import("date-fns/locale/pt-BR").then((module) => module.ptBR),
  ar: () => import("date-fns/locale/ar").then((module) => module.ar),
  tr: () => import("date-fns/locale/tr").then((module) => module.tr),
  ko: () => import("date-fns/locale/ko").then((module) => module.ko),
  hi: () => import("date-fns/locale/hi").then((module) => module.hi),
  vi: () => import("date-fns/locale/vi").then((module) => module.vi),
  "zh-Hant": () => import("date-fns/locale/zh-TW").then((module) => module.zhTW),
  ja: () => import("date-fns/locale/ja").then((module) => module.ja),
  id: () => import("date-fns/locale/id").then((module) => module.id),
};

const loaded = new Map<LanguageCode, Promise<Locale>>();

function loadLocale(language: LanguageCode) {
  let locale = loaded.get(language);
  if (!locale) {
    locale = LOADERS[language]();
    loaded.set(language, locale);
  }
  return locale;
}

/**
 * The date-fns locale of the interface language. It suspends until the locale has loaded, so render the widget
 * inside a Suspense boundary (or accept that its parent suspends briefly the first time).
 */
export function useDateFnsLocale(): Locale {
  return use(loadLocale(useLocale()));
}
