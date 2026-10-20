"use client";

import { useFormatter, useTranslations } from "use-intl";

import { CALENDAR_DAY, dayOf } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";

import type { Gap, ThreadSummary } from "../../domain/contract-threads";
import { rhythmOf, rowStatus } from "../../domain/phrases";

/*
 * The Hub's recurring phrases in the interface language: dates, gaps, a row's status line, rhythms and
 * quotes. Даты встреч и сроки — календарные дни: у момента берётся его день в поясе кабинета, а день печатается
 * в UTC, где лежит его полночь.
 */
export function useHubPhrases() {
  const t = useTranslations("hub");
  const format = useFormatter();
  const zone = useTimeZone();
  const date = (iso: string) => format.dateTime(new Date(dayOf(iso, zone)), "short", CALENDAR_DAY);
  const gap = (value: Gap) => t(`gap.${value.kind}`, { days: value.days });
  const quote = (text: string) => t("quote", { text });
  return {
    date,
    gap,
    quote,
    /** Several dates in a row: "Sep 12, Sep 19, Sep 26". */
    dates: (isos: string[]) => format.list(isos.map(date), { type: "unit", style: "short" }),
    /** Things said, each in the language's quotes: “a”, “b”. */
    quotes: (items: string[]) => format.list(items.map(quote), { type: "unit", style: "short" }),
    rhythm: (days: number) => t("rhythm", rhythmOf(days)),
    /** "under discussion · overdue by 4 days": the stage, then what is missing. */
    status: (thread: ThreadSummary) => {
      const status = rowStatus(thread);
      const parts = [t(`stage.${status.stage}`)];
      if (status.gap) parts.push(gap(status.gap));
      else if (status.circles !== null) parts.push(t("discussedNoDecision", { count: status.circles }));
      return parts.join(" · ");
    },
  };
}
