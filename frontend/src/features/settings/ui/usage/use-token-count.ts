"use client";

import { useFormatter, useTranslations } from "next-intl";

/** Token counts for people, in the interface language: "1.3M tokens", "1,3 млн токенов". */
export function useTokenCount() {
  const t = useTranslations("settingsUsage");
  const format = useFormatter();
  return {
    /** The compact number alone, "1.3M", for messages that word the tokens themselves. */
    amount: (count: number) => format.number(count, "compact"),
    /** "1.3M tokens". */
    tokens: (count: number) => t("tokens", { count, amount: format.number(count, "compact") }),
  };
}
