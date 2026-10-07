"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatBytes } from "@/i18n/format-units";

import type { FileItem } from "../domain/contract";
import { leoBlocker } from "../domain/files";

/** Why Leo can't use a file, in the interface language; null when it can. */
export function useLeoBlocker() {
  const t = useTranslations("fileManager");
  const locale = useLocale();
  return (file: Pick<FileItem, "name" | "size_bytes" | "leo_readable">): string | null => {
    const blocker = leoBlocker(file);
    if (!blocker) return null;
    if (blocker.reason === "tooLarge") return t("leo.tooLarge", { size: formatBytes(locale, blocker.maxBytes) });
    if (blocker.reason === "extension") return t("leo.extension", { extension: blocker.extension });
    return t("leo.unknownType");
  };
}
