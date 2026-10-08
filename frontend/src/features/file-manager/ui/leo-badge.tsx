"use client";

import { CircleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";

import { IN_PROGRESS, type LeoUse } from "../domain/contract";
import { LeoFileIcon } from "./leo-file-icon";

/** "Leo", "Leo · reading 40%" or "Leo · couldn’t read": whether Leo uses a file and how far it got. */
export function LeoBadge({ leo, className }: { leo: LeoUse | null; className?: string }) {
  const t = useTranslations("fileManager");
  if (!leo) return null;
  const via = leo.via === "folder" ? t("leo.viaFolder") : t("leo.viaFile");
  if (leo.status === "failed")
    return (
      <Badge variant="destructive" className={className} title={leo.error ?? undefined}>
        <CircleAlert aria-hidden="true" />
        {t("leo.failed")}
      </Badge>
    );
  if (IN_PROGRESS.has(leo.status))
    return (
      <Badge variant="secondary" className={className} title={via}>
        <Spinner aria-hidden="true" />
        {t("leo.reading")}
      </Badge>
    );
  return (
    <Badge variant="secondary" className={className} title={via}>
      <LeoFileIcon />
      Leo
    </Badge>
  );
}
