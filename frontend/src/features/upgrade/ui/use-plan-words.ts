"use client";

import { useFormatter, useLocale, useTranslations } from "use-intl";

import { formatBytes } from "@/i18n/format-units";

import type { Cell, Highlight, Storage } from "../domain/plan-features";

/** Words for the plan cards and the comparison table, in the interface language. */
export function usePlanWords() {
  const t = useTranslations("upgradePlans");
  const locale = useLocale();
  const format = useFormatter();

  const storage = (value: Storage) => {
    if (value === "unlimited") return t("storage.unlimited");
    const amount = formatBytes(locale, value.bytes);
    if (value.basis === "perUser") return t("storage.perUser", { amount });
    if (value.basis === "from") return t("storage.from", { amount });
    return amount;
  };

  const highlight = (line: Highlight): string => {
    switch (line.kind) {
      case "custom":
        return line.text;
      case "meetings":
        if (line.minutes === null) return t("highlights.unlimitedMeetings");
        return line.included ? t("highlights.meetingMinutes", { minutes: line.minutes }) : t("highlights.noMeetings");
      case "fileManager":
        return line.storage
          ? t("highlights.fileManager", { storage: storage(line.storage) })
          : t("highlights.noFileManager");
      case "knowledge":
        return line.storage
          ? t("highlights.knowledge", { storage: storage(line.storage) })
          : t("highlights.noKnowledge");
      case "capability":
        return t(`capabilities.${line.capability}`);
    }
  };

  /** A comparison cell with a value; yes/no cells are marks, drawn by the table. */
  const cell = (value: Exclude<Cell, boolean>): string => {
    switch (value.kind) {
      case "unlimited":
        return t("compare.unlimited");
      case "minutes":
        return t("compare.minutes", { minutes: value.minutes });
      case "storage":
        return storage(value.storage);
      case "users":
        if (value.max === value.min) return format.number(value.min);
        return value.max === null
          ? t("compare.usersOpen", { min: value.min })
          : t("compare.users", { min: value.min, max: value.max });
      case "customUsers":
        return t("compare.customUsers");
    }
  };

  return { storage, highlight, cell };
}
