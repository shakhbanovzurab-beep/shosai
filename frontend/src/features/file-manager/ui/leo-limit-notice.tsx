"use client";

import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import { useStorage } from "../model/storage-resource";
import { LeoFileIcon } from "./leo-file-icon";

/**
 * Leo uses more of the files than the plan's knowledge base holds (FL-D10): it keeps reading everything until
 * the named date, then stops reading the newest files over the limit. Nothing is deleted.
 */
export function LeoLimitNotice() {
  const t = useTranslations("fileManager");
  const format = useFormatter();
  const locale = useLocale();
  const storage = useStorage();
  if (storage.status !== "ready" || !storage.data.leo_removal_at) return null;
  const { leo_used_bytes: used, leo_limit_bytes: limit, leo_removal_at: date } = storage.data;
  return (
    <Alert variant="destructive" role="status">
      <LeoFileIcon />
      <AlertTitle>
        {t("leoLimit.title", { used: formatBytes(locale, used), limit: formatBytes(locale, limit ?? 0) })}
      </AlertTitle>
      <AlertDescription>
        <p>{t("leoLimit.description", { date: format.dateTime(new Date(date), { dateStyle: "long" }) })}</p>
        <p>
          <Link href="/app/upgrade">{t("storage.upgrade")}</Link>
        </p>
      </AlertDescription>
    </Alert>
  );
}
