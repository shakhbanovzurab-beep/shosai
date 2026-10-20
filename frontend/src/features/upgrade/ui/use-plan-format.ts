"use client";

import { useFormatter } from "use-intl";

import { CALENDAR_DAY } from "@/i18n/calendar-days";

/** Prices and reset days in the interface language: 1500 cents in "USD" → "$15" / "15 $US"; cents only when the price has them. */
export function usePlanFormat() {
  const format = useFormatter();
  return {
    price: (cents: number, currency: string) => {
      const digits = cents % 100 === 0 ? 0 : 2;
      return format.number(cents / 100, {
        style: "currency",
        currency,
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
    },
    /** День, когда обнуляются минуты, «1 ноября»: `resets_at` — полночь UTC, и день печатается в UTC. */
    resetDay: (iso: string) => format.dateTime(new Date(iso), { month: "long", day: "numeric", ...CALENDAR_DAY }),
  };
}
