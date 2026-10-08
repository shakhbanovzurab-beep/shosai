"use client";

import { toast } from "sonner";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { formatBytes } from "@/i18n/format-units";

import { MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS } from "../domain/contract";
import { limitAttachments } from "../domain/tickets";

/** Adds files, keeping within the limits and telling the user, in the interface language, what was skipped. */
export function useAddFiles() {
  const t = useTranslations("pagesSupport");
  const format = useFormatter();
  const locale = useLocale();
  return (current: File[], incoming: File[]): File[] => {
    const { files, tooBig, overLimit } = limitAttachments(current, incoming);
    if (tooBig.length) {
      const names = format.list(tooBig.map((f) => f.name));
      const size = formatBytes(locale, MAX_ATTACHMENT_BYTES);
      toast.error(t("attach.tooBig", { count: tooBig.length, names, size }));
    }
    if (overLimit) toast.error(t("attach.tooMany", { max: MAX_ATTACHMENTS }));
    return files;
  };
}
