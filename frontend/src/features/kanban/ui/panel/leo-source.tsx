"use client";

import { ExternalLink, Sparkles } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Link } from "@/lib/navigation";

import type { TaskSource } from "../../domain/tasks-contract";

/** «Заполнил Лео» в строке поля: откуда он это взял — встреча, момент и слова; ссылка на этот момент встречи. */
export function LeoSource({ source }: { source: TaskSource }) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  const meeting = source.meeting;
  const seconds = source.finding ? Math.floor(source.finding.start_ms / 1000) : 0;
  // Момент встречи: часы — только у длинной встречи («1:05:00»), иначе минуты и секунды.
  const time = format.dateTime(new Date(seconds * 1000), {
    ...(seconds >= 3600 ? { hour: "numeric" as const, hourCycle: "h23" as const } : {}),
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  });
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="xs" className="text-violet-700 dark:text-violet-300">
          <Sparkles data-icon="inline-start" />
          {t("leo.filled")}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="flex w-80 flex-col gap-3 text-sm">
        {meeting ? (
          <p>
            {t("leo.from", {
              meeting: meeting.title,
              date: format.dateTime(new Date(meeting.started_at), "medium"),
            })}
          </p>
        ) : null}
        {source.finding ? (
          <figure className="flex flex-col gap-1">
            <figcaption className="text-muted-foreground text-xs">{t("leo.said", { time })}</figcaption>
            <blockquote dir="auto" className="border-s-2 ps-3 italic">
              {source.finding.quote}
            </blockquote>
          </figure>
        ) : null}
        {meeting ? (
          <Button asChild variant="outline" size="sm" className="self-start">
            <Link href={`/app/notes/${encodeURIComponent(meeting.id)}?t=${seconds}`}>
              <ExternalLink data-icon="inline-start" className="rtl:-scale-x-100" />
              {t("leo.open")}
            </Link>
          </Button>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
