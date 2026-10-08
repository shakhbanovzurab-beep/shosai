import { useFormatter } from "use-intl";

/** A task's due day in the user's language ("Jun 26", "26 июн."); `date` is a calendar day, "2026-06-26". */
export function DueDate({ date }: { date: string }) {
  const format = useFormatter();
  // A calendar day parses as UTC midnight, and next-intl formats in UTC, so the day never shifts.
  return <time dateTime={date}>{format.dateTime(new Date(date), "short")}</time>;
}
