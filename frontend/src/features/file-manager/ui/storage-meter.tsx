"use client";

import { cn } from "cn";
import { HardDrive } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import type { StorageStanding } from "../domain/contract";
import { useStorage } from "../model/storage-resource";

/**
 * How much of the plan's storage the files take. Over the limit (FL-D2) everything stays and only new uploads
 * wait; the notice names the date the newest files over the limit go, and how to avoid it.
 */
export function StorageMeter() {
  const storage = useStorage();
  if (storage.status !== "ready") return null;
  return (
    <div className="flex flex-col gap-3">
      <StorageBar standing={storage.data} />
      {storage.data.removal_at ? <OverLimitNotice date={storage.data.removal_at} /> : null}
    </div>
  );
}

function StorageBar({ standing }: { standing: StorageStanding }) {
  const t = useTranslations("fileManager");
  const locale = useLocale();
  const used = formatBytes(locale, standing.used_bytes);
  const limit = standing.limit_bytes;
  if (limit === null || limit === 0) return null;
  const over = standing.used_bytes > limit;
  return (
    <section aria-label={t("storage.label")} className="flex flex-col gap-2 rounded-xl border bg-card p-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-2 font-medium">
          <HardDrive className="size-4 text-muted-foreground" aria-hidden="true" />
          {t("storage.title")}
        </span>
        <span className="text-muted-foreground text-xs tabular-nums">
          {t("storage.ratio", { used, limit: formatBytes(locale, limit) })}
        </span>
      </div>
      <Progress
        value={Math.min(100, (standing.used_bytes / limit) * 100)}
        aria-label={t("storage.ratio", { used, limit: formatBytes(locale, limit) })}
        className={cn(over && "*:data-[slot=progress-indicator]:bg-destructive")}
      />
    </section>
  );
}

function OverLimitNotice({ date }: { date: string }) {
  const t = useTranslations("fileManager");
  const format = useFormatter();
  return (
    <Alert variant="destructive" role="status">
      <HardDrive aria-hidden="true" />
      <AlertTitle>{t("storage.overTitle")}</AlertTitle>
      <AlertDescription>
        <p>{t("storage.overDescription", { date: format.dateTime(new Date(date), { dateStyle: "long" }) })}</p>
        <p>
          <Link href="/app/upgrade">{t("storage.upgrade")}</Link>
        </p>
      </AlertDescription>
    </Alert>
  );
}
