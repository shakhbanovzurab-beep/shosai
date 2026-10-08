"use client";

import { useFormatter } from "use-intl";

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
    /** The day the meeting minutes reset, "November 1"; `resets_at` is UTC midnight and next-intl formats in UTC. */
    resetDay: (iso: string) => format.dateTime(new Date(iso), { month: "long", day: "numeric" }),
  };
}
