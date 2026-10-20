"use client";

import { useFormatter, useNow, useTranslations } from "use-intl";

import { useTimeZone } from "@/i18n/time-zone";

import { isRecentMail, replyDue } from "../domain/mail-dates";

/*
 * Когда письмо пришло или получило ответ — момент на часах человека, а не календарный день: его печатает
 * форматтер в поясе кабинета, в нём же считаются дни до срока ответа.
 */

/** Dates in the inbox, in the interface language: list dates, full timestamps, reply-by labels. */
export function useMailDates() {
  const format = useFormatter();
  const t = useTranslations("mailLeo");
  const now = useNow({ updateInterval: 60_000 });
  const zone = useTimeZone();

  /** "2 hours ago" for the last few days, else "Mar 5, 2026". */
  const listDate = (iso: string) => {
    const date = new Date(iso);
    // Something newer than the last tick reads "now", never "in 20 seconds".
    if (isRecentMail(iso, now)) return { isRecent: true, text: format.relativeTime(Math.min(+date, +now), now) };
    return { isRecent: false, text: format.dateTime(date, "medium") };
  };

  /** The full timestamp above an open email: "Mar 5, 2026, 9:30 AM". */
  const timestamp = (iso: string) => format.dateTime(new Date(iso), "dateTime");

  /** "Overdue", "Reply today", "Reply tomorrow", "Reply by Fri" or "Reply by Oct 14". */
  const replyBy = (iso: string) => {
    const due = replyDue(iso, now, zone);
    const isOverdue = due === "overdue";
    if (due === "overdue" || due === "today" || due === "tomorrow") return { label: t(`replyBy.${due}`), isOverdue };
    const when = format.dateTime(new Date(iso), due === "thisWeek" ? "weekdayName" : "short");
    return { label: t("replyBy.by", { when }), isOverdue };
  };

  return { listDate, timestamp, replyBy };
}
