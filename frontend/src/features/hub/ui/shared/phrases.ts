"use client";

import { useFormatter, useTranslations } from "use-intl";

import type { Gap, ThreadSummary } from "../../domain/contract-threads";
import { rhythmOf, rowStatus } from "../../domain/phrases";

/*
 * The Hub's recurring phrases in the interface language: dates, gaps, a row's status line, rhythms and
 * quotes. Dates of meetings and due dates are calendar days, formatted in UTC like the demo data.
 */
export function useHubPhrases() {
  const t = useTranslations("hub");
  const format = useFormatter();
  const date = (iso: string) => format.dateTime(new Date(iso), "short");
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
