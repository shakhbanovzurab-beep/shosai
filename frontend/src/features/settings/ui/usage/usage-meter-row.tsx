"use client";

import { cn } from "cn";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Progress } from "@/components/ui/progress";
import { formatBytes } from "@/i18n/format-units";

import type { MeterTone } from "../../domain/usage-meters";
import type { UsageRow } from "../../model/usage-overview";
import { useTokenCount } from "./use-token-count";

// Предупреждающего токена в теме нет; янтарь — цвет «заканчивается» в кабинете (admin-errors, профиль).
const NOTE: Record<MeterTone, string> = {
  ok: "text-muted-foreground",
  low: "text-amber-700 dark:text-amber-300",
  full: "text-destructive",
};
const BAR: Record<MeterTone, string | undefined> = {
  ok: undefined,
  low: "*:data-[slot=progress-indicator]:bg-amber-500",
  full: "*:data-[slot=progress-indicator]:bg-destructive",
};

type Words = ReturnType<typeof useRowWords>;

function useRowWords() {
  const t = useTranslations("settingsUsage");
  const format = useFormatter();
  const locale = useLocale();
  const tokens = useTokenCount();
  return {
    t,
    weekday: (iso: string) => format.dateTime(new Date(iso), "weekdayTime"),
    day: (iso: string) => format.dateTime(new Date(iso), { month: "long", day: "numeric" }),
    bytes: (value: number) => formatBytes(locale, value),
    ...tokens,
  };
}

function label(row: UsageRow, { t }: Words) {
  if (row.kind === "standard" || row.kind === "frontier") return t(`tiers.${row.kind}.title`);
  return t(`overview.kinds.${row.kind}`);
}

/** «1,2M из 2M токенов», «45 из 120 мин», «2,3 ГБ из 10 ГБ»; без лимита — сколько уже и «без лимита». */
function amount(row: UsageRow, w: Words) {
  const { t } = w;
  if (row.kind === "minutes") {
    if (row.limit === null) return t("overview.noLimit", { used: t("overview.minutesUsed", { used: row.used }) });
    return t("overview.minutesOf", { used: row.used, limit: row.limit });
  }
  if (row.kind === "storage" || row.kind === "knowledge") {
    if (row.limit === null) return t("overview.noLimit", { used: w.bytes(row.used) });
    return t("overview.bytesOf", { used: w.bytes(row.used), limit: w.bytes(row.limit) });
  }
  if (row.limit === null) return t("overview.noLimit", { used: w.tokens(row.used) });
  return t("used", { count: row.limit, used: w.amount(row.used), limit: w.amount(row.limit) });
}

/** Строка под полосой: когда сброс, и что значит «заканчивается» или «исчерпано» именно для этого лимита. */
function note(row: UsageRow, w: Words, unlimitedMinutesPlan: string | null): string | null {
  const { t } = w;
  // Без лимита нечего сбрасывать и не о чем предупреждать.
  if (row.limit === null) return null;
  if (row.kind === "frontier" && row.tone === "low" && row.share === 1)
    return t("overview.notes.frontierExtra", { amount: w.amount(row.extraTokens) });
  if (row.kind === "minutes" && row.tone === "full" && row.resetsAt) {
    const date = w.day(row.resetsAt);
    return unlimitedMinutesPlan
      ? t("overview.notes.minutesPausedUpgrade", { date, plan: unlimitedMinutesPlan })
      : t("overview.notes.minutesPaused", { date });
  }
  if (row.resetsAt) {
    const date = row.kind === "minutes" ? w.day(row.resetsAt) : w.weekday(row.resetsAt);
    if (row.tone === "full") return t("overview.notes.fullResets", { date });
    return row.tone === "low" ? t("overview.notes.lowResets", { date }) : t("overview.notes.resets", { date });
  }
  if (row.tone === "full")
    return row.kind === "storage" ? t("overview.notes.storageFull") : t("overview.notes.knowledgeFull");
  return row.tone === "low" ? t("overview.notes.low") : null;
}

/** Одна шкала вида использования. */
export function UsageMeterRow({ row, unlimitedMinutesPlan }: { row: UsageRow; unlimitedMinutesPlan: string | null }) {
  const words = useRowWords();
  const format = useFormatter();
  const title = label(row, words);
  const text = note(row, words, unlimitedMinutesPlan);
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-sm">
        <span className="font-medium">{title}</span>
        <span className="text-muted-foreground tabular-nums">{amount(row, words)}</span>
      </div>
      {row.share === null ? null : (
        <Progress
          value={row.share * 100}
          aria-label={words.t("overview.meterLabel", { label: title, percent: format.number(row.share, "percent") })}
          className={BAR[row.tone]}
        />
      )}
      {text ? <p className={cn("text-xs", NOTE[row.tone])}>{text}</p> : null}
    </div>
  );
}
