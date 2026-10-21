"use client";

import { Video } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import type { TaskSource } from "../../domain/tasks-contract";

/** Откуда задача: встреча со ссылкой на её страницу, или что встречи больше нет (TK-D3). */
export function PanelSource({ source }: { source: TaskSource }) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  if (source.kind !== "meeting") return null;
  if (!source.meeting) return <p className="text-muted-foreground text-sm">{t("source.gone")}</p>;
  const date = format.dateTime(new Date(source.meeting.started_at), "medium");
  return (
    <p className="flex items-center gap-2 text-muted-foreground text-sm">
      <Video className="size-4 shrink-0" aria-hidden="true" />
      <Link
        href={`/app/notes/${encodeURIComponent(source.meeting.id)}`}
        className="underline-offset-4 hover:text-foreground hover:underline"
      >
        {t("source.meeting", { meeting: source.meeting.title, date })}
      </Link>
    </p>
  );
}
