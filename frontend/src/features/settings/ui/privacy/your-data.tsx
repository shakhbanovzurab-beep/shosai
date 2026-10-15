"use client";

import { Download } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useLatestExport, useRequestExport } from "@/features/identity/model/account-export";
import { formatBytes } from "@/i18n/format-units";
import { apiErrorDescription } from "@/lib/api/error-description";

import { SettingsGroup, SettingsRow } from "../settings-row";

/** Privacy › Your data: архив всего, что Shosai хранит о человеке; собирается в фоне и приходит письмом. */
export function YourData() {
  const t = useTranslations("settingsPrivacy");
  const format = useFormatter();
  const locale = useLocale();
  const latest = useLatestExport();
  const request = useRequestExport();
  const job = latest.data ?? null;
  const preparing = job?.state === "queued" || job?.state === "running" || request.isPending;

  const start = () =>
    request.mutate(undefined, {
      onError: (error) => toast.error(t("exportFailed"), { description: apiErrorDescription(error) }),
    });

  let status: string | null = null;
  if (preparing) status = t("exportPreparing");
  else if (job?.state === "failed") status = t("exportFailed");
  else if (job?.state === "ready" && job.download_expires_at) {
    const size = formatBytes(locale, job.size_bytes ?? 0);
    status = t("exportReady", { size, date: format.dateTime(new Date(job.download_expires_at), "dateTime") });
  }

  return (
    <SettingsGroup title={t("yourData")}>
      <SettingsRow title={t("export")} description={t("exportHint")}>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {job?.state === "ready" && job.download_url ? (
            <Button variant="outline" asChild>
              <a href={job.download_url} download>
                <Download data-icon="inline-start" />
                {t("exportDownload")}
              </a>
            </Button>
          ) : null}
          <Button variant="outline" disabled={preparing || latest.isPending} onClick={start}>
            {preparing ? <Spinner data-icon="inline-start" /> : null}
            {job === null ? t("exportStart") : t("exportAgain")}
          </Button>
        </div>
      </SettingsRow>
      {status ? (
        <p aria-live="polite" className="text-muted-foreground text-sm">
          {status}
        </p>
      ) : null}
    </SettingsGroup>
  );
}
