"use client";

import { cn } from "cn";
import { Clock, Timer as StopwatchIcon } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { formatSpan } from "@/i18n/format-units";

import type { Card } from "../domain/tasks-contract";
import { columnTime, trackingSums } from "../domain/time-rules";
import { useBoardSelector, useBoardStickers, useColumn } from "../model/board-hooks";
import { useServerMinuteWhile } from "../model/server-clock";
import { useVisibleCardIds } from "./filters/use-visible-cards";

/*
 * Суммы времени колонки по карточкам, которые она показывает (под фильтром — по совпавшим): время в колонке, когда
 * доска считает его по колонкам (KT-D2), и Σ факта к Σ плана, когда доска ведёт учёт (KT-D4).
 */

const MINUTE_MS = 60_000;

type ColumnClock = { cards: Record<string, Card>; running: boolean; now: number; total: number | null };

// Колонка пересчитывает время, только когда меняются её карточки или минута: шаг перетаскивания в другой колонке,
// правка карточки в соседней — не повод обходить сотни карточек этой (замер на «Load 1000», шаг 4 пакета).
const clockCache = new WeakMap<string[], ColumnClock>();

function columnClock(ids: string[], cards: Record<string, Card>): ColumnClock {
  const hit = clockCache.get(ids);
  if (hit?.cards === cards) return hit;
  const made = { cards, running: ids.some((id) => Boolean(cards[id]?.stopwatch?.running_since)), now: -1, total: null };
  clockCache.set(ids, made);
  return made;
}

function columnTotal(ids: string[], cards: Record<string, Card>, columnId: string, now: number) {
  const clock = columnClock(ids, cards);
  if (clock.now !== now) Object.assign(clock, { now, total: columnTime(ids, cards, columnId, now) });
  return clock.total;
}

const trackingCache = new WeakMap<string[], { cards: Record<string, Card>; key: string | null }>();

/** Σ плана и факта колонки строкой «план:факт» (одно значение для подписки), с тем же кешем по карточкам колонки. */
function trackingKey(ids: string[], cards: Record<string, Card>) {
  const hit = trackingCache.get(ids);
  if (hit?.cards === cards) return hit.key;
  const sums = trackingSums(ids, cards);
  const key = sums ? `${sums.plan}:${sums.fact}` : null;
  trackingCache.set(ids, { cards, key });
  return key;
}

const LINE = "flex min-w-0 items-center gap-1 text-muted-foreground text-xs tabular-nums leading-none";

function ColumnStopwatch({ columnId }: { columnId: string }) {
  const t = useTranslations("kanban");
  const locale = useLocale();
  const title = useColumn(columnId)?.title ?? "";
  const ids = useVisibleCardIds(columnId);
  // Минута нужна, только пока в колонке что-то идёт.
  const running = useBoardSelector((s) => columnClock(ids, s.cards).running);
  const now = useServerMinuteWhile(running);
  const total = useBoardSelector((s) => columnTotal(ids, s.cards, columnId, now));
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
  const sums = useBoardSelector((s) => trackingKey(ids, s.cards));
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
