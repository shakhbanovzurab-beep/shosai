"use client";

import { useFormatter, useNow, useTranslations } from "next-intl";

import { isRecentMail, replyDue } from "../domain/mail-dates";

/*
 * When an email arrived or was answered is a moment on the viewer's own clock, not a calendar day, so these
 * dates are formatted in the browser's time zone rather than next-intl's UTC. The inbox renders only after
 * mount (MailPanels in mail-inbox.tsx), so nothing here is server rendered and hydration can't mismatch.
 */
const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

/** Dates in the inbox, in the interface language: list dates, full timestamps, reply-by labels. */
export function useMailDates() {
  const format = useFormatter();
  const t = useTranslations("mailLeo");
  const now = useNow({ updateInterval: 60_000 });
  const timeZone = viewerTimeZone();

  /** "2 hours ago" for the last few days, else "Mar 5, 2026". */
  const listDate = (iso: string) => {
    const date = new Date(iso);
    // Something newer than the last tick reads "now", never "in 20 seconds".
    if (isRecentMail(iso, now)) return { isRecent: true, text: format.relativeTime(Math.min(+date, +now), now) };
    return { isRecent: false, text: format.dateTime(date, "medium", { timeZone }) };
  };

  /** The full timestamp above an open email: "Mar 5, 2026, 9:30 AM". */
  const timestamp = (iso: string) => format.dateTime(new Date(iso), "dateTime", { timeZone });

  /** "Overdue", "Reply today", "Reply tomorrow", "Reply by Fri" or "Reply by Oct 14". */
  const replyBy = (iso: string) => {
    const due = replyDue(iso, now);
    const isOverdue = due === "overdue";
    if (due === "overdue" || due === "today" || due === "tomorrow") return { label: t(`replyBy.${due}`), isOverdue };
    const when = format.dateTime(new Date(iso), due === "thisWeek" ? "weekdayName" : "short", { timeZone });
    return { label: t("replyBy.by", { when }), isOverdue };
  };

  return { listDate, timestamp, replyBy };
}
