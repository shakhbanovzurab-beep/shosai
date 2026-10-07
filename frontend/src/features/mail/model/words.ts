import type { useTranslations } from "next-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translators in (`useMailWords()` in the UI).
 */

export type MailWords = {
  mail: ReturnType<typeof useTranslations<"mail">>;
  leo: ReturnType<typeof useTranslations<"mailLeo">>;
  common: ReturnType<typeof useTranslations<"common">>;
};
