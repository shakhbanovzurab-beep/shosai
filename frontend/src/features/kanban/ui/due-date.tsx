import { useFormatter } from "use-intl";

import { CALENDAR_DAY } from "@/i18n/calendar-days";

/** A task's due day in the user's language ("Jun 26", "26 июн."); `date` is a calendar day, "2026-06-26". */
export function DueDate({ date }: { date: string }) {
  const format = useFormatter();
  // Календарный день — полночь UTC; печатается в UTC, поэтому не сдвигается ни в каком поясе.
  return <time dateTime={date}>{format.dateTime(new Date(date), "short", CALENDAR_DAY)}</time>;
}
