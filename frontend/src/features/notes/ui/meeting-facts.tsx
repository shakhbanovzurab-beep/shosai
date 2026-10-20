import { CalendarDays, Clock } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { MetaItem } from "@/components/meta-item";

import { formatMeetingDuration } from "../domain/format";

interface MeetingFactsProps {
  readonly startedAt: string;
  readonly durationMinutes: number;
}

/**
 * When a meeting was and how long it ran, for the row of facts under its title, in the interface language.
 * Начало печатается в поясе кабинета, его даёт форматтер.
 */
export function MeetingFacts({ startedAt, durationMinutes }: MeetingFactsProps) {
  const t = useTranslations("notes");
  const format = useFormatter();
  const locale = useLocale();
  return (
    <>
      <MetaItem icon={CalendarDays} label={t("fields.date")} className="shrink-0">
        <time dateTime={startedAt}>{format.dateTime(new Date(startedAt), "weekdayDateTime")}</time>
      </MetaItem>
      <MetaItem icon={Clock} label={t("fields.duration")} className="shrink-0">
        {formatMeetingDuration(locale, durationMinutes)}
      </MetaItem>
    </>
  );
}
