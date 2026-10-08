"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import type { LeoUse } from "@/features/file-manager/domain/contract";

import { PIPELINE, pipelineProgress } from "../model/leo-files";

/** Where a file is in parse → chunk → embed → index, with overall progress while it runs. */
export function FileStatusCell({ name, leo }: { name: string; leo: LeoUse }) {
  const t = useTranslations("knowledgeBase");
  const format = useFormatter();
  if (leo.status === "indexed") {
    return (
      <Badge variant="secondary" className="gap-1 rounded-md">
        <CircleCheck className="text-emerald-600 dark:text-emerald-400" />
        {t("steps.indexed")}
      </Badge>
    );
  }
  if (leo.status === "failed") {
    return (
      <div className="flex min-w-0 flex-col gap-1">
        <Badge variant="destructive" className="w-fit gap-1 rounded-md">
          <CircleAlert />
          {t("steps.failed")}
        </Badge>
        {leo.error ? (
          <span className="truncate text-muted-foreground text-xs" dir="auto">
            {leo.error}
          </span>
        ) : null}
      </div>
    );
  }

  const { step, overall } = pipelineProgress(leo);
  const label = t(`steps.${leo.status}`);
  return (
    <div className="flex w-40 flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-sm">
        <Spinner className="size-3.5 text-muted-foreground" />
        {label}
        <span className="text-muted-foreground text-xs tabular-nums">
          {t("status.step", { step: step + 1, total: PIPELINE.length })}
        </span>
      </span>
      <Progress
        value={overall}
        aria-label={t("status.progress", { name, step: label, percent: format.number(overall / 100, "percent") })}
      />
    </div>
  );
}
