"use client";

import { useTranslations } from "next-intl";

import type { MailWords } from "../model/words";

/** The translators the mail actions word their toasts with. */
export function useMailWords(): MailWords {
  return { mail: useTranslations("mail"), leo: useTranslations("mailLeo"), common: useTranslations("common") };
}
