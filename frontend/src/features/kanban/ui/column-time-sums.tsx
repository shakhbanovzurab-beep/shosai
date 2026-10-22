"use client";

import { cn } from "cn";
import { Clock, Timer as StopwatchIcon } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { formatSpan } from "@/i18n/format-units";

import { columnTime, trackingSums } from "../domain/time-rules";
import { useBoardSelector, useBoardStickers, useColumn } from "../model/board-hooks";
import { useServerMinuteWhile } from "../model/server-clock";
import { useVisibleCardIds } from "./filters/use-visible-cards";

/*
 * Суммы времени колонки по карточкам, которые она показывает (под фильтром — по совпавшим): время в колонке, когда
 * доска считает его по колонкам (KT-D2), и Σ факта к Σ плана, когда доска ведёт учёт (KT-D4).
 */

const MINUTE_MS = 60_000;
const LINE = "flex min-w-0 items-center gap-1 text-muted-foreground text-xs tabular-nums leading-none";

function ColumnStopwatch({ columnId }: { columnId: string }) {
  const t = useTranslations("kanban");
  const locale = useLocale();
  const title = useColumn(columnId)?.title ?? "";
  const ids = useVisibleCardIds(columnId);
  // Минута нужна, только пока в колонке что-то идёт.
  const running = useBoardSelector((s) => ids.some((id) => Boolean(s.cards[id]?.stopwatch?.running_since)));
  const now = useServerMinuteWhile(running);
  const total = useBoardSelector((s) => columnTime(ids, s.cards, columnId, now));
  if (total === null) return null;
  const time = formatSpan(locale, total);
  return (
    <p className={LINE}>
      <StopwatchIcon className="size-3 shrink-0" aria-hidden="true" />
      <span aria-hidden="true">{time}</span>
      <span className="sr-only">{t("column.timeLabel", { column: title, time })}</span>
    </p>
  );
}

function ColumnTracking({ columnId }: { columnId: string }) {
  const t = useTranslations("kanban");
  const locale = useLocale();
  const title = useColumn(columnId)?.title ?? "";
  const ids = useVisibleCardIds(columnId);
  const sums = useBoardSelector((s) => {
    const found = trackingSums(ids, s.cards);
    return found ? `${found.plan}:${found.fact}` : null;
  });
  if (sums === null) return null;
  const [plan = 0, fact = 0] = sums.split(":").map(Number);
  const span = (minutes: number) => formatSpan(locale, minutes * MINUTE_MS);
  return (
    <p className={LINE}>
      <Clock className="size-3 shrink-0" aria-hidden="true" />
      <span aria-hidden="true">
        <span className={cn(fact > plan && plan > 0 && "text-destructive")}>{span(fact)}</span> / {span(plan)}
      </span>
      <span className="sr-only">
        {t("column.trackingLabel", { column: title, fact: span(fact), plan: span(plan) })}
      </span>
    </p>
  );
}

/** Суммы времени колонки — только у полей, которые доска показывает. */
export function ColumnTimeSums({ columnId }: { columnId: string }) {
  const stickers = useBoardStickers();
  const stopwatch = stickers.find((sticker) => sticker.id === "stopwatch");
  const tracking = stickers.find((sticker) => sticker.id === "time_tracking");
  return (
    <>
      {stopwatch?.visible && stopwatch.automations?.restart_on_move ? <ColumnStopwatch columnId={columnId} /> : null}
      {tracking?.visible ? <ColumnTracking columnId={columnId} /> : null}
    </>
  );
}
