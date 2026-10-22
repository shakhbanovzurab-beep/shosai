"use client";

import type { ReactNode } from "react";

import { cn } from "cn";
import { Clock, Hourglass, Pause, Timer as StopwatchIcon } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { formatSpan } from "@/i18n/format-units";

import type { TimeStickerId } from "../../domain/stickers-contract";
import type { Card } from "../../domain/tasks-contract";
import type { Stopwatch, Timer, TimeTracking } from "../../domain/time-contract";
import { overPlan, stopwatchElapsed, timerLeft } from "../../domain/time-rules";
import { useServerMinute } from "../../model/server-clock";
import { Chip } from "./chip";

/*
 * Время на карточке (KT-D6): секундомер — пока идёт, таймер — пока задан, план и факт — когда есть. Идущие часы
 * слушают один минутный такт доски по серверу; остановленные и на паузе не слушают ничего.
 */

const MINUTE_MS = 60_000;

/** Идущий секундомер: закрытые отрезки и идущий. */
function StopwatchChip({ stopwatch }: { stopwatch: Stopwatch }) {
  const t = useTranslations("kanban");
  const locale = useLocale();
  const now = useServerMinute();
  const elapsed = stopwatchElapsed(stopwatch, now);
  return (
    <Chip>
      <StopwatchIcon className="size-3 shrink-0" aria-hidden="true" />
      <span className="sr-only">{t("card.time.stopwatch")}</span>
      <span className="truncate tabular-nums">{formatSpan(locale, elapsed)}</span>
    </Chip>
  );
}

/** Таймер с остатком: до нуля — сколько осталось, после — «Время вышло» и перерасход. `children` — отметка паузы. */
function TimerFace({ left, children }: { left: number; children?: ReactNode }) {
  const t = useTranslations("kanban");
  const locale = useLocale();
  // Остаток меньше минуты — ещё «1 мин», а не «0 мин»: время вышло только на нуле.
  const up = left <= 0;
  const shown = up ? formatSpan(locale, -left) : formatSpan(locale, Math.max(left, MINUTE_MS));
  return (
    <Chip tone={up ? "alert" : "quiet"}>
      <Hourglass className="size-3 shrink-0" aria-hidden="true" />
      <span className="sr-only">{t("card.time.timer")}</span>
      <span className="truncate tabular-nums">
        {up ? t("card.time.timeUp", { over: shown }) : t("card.time.left", { left: shown })}
      </span>
      {children}
    </Chip>
  );
}

function RunningTimer({ timer }: { timer: Timer }) {
  const now = useServerMinute();
  return <TimerFace left={timerLeft(timer, now)} />;
}

function TimerChip({ timer }: { timer: Timer }) {
  const t = useTranslations("kanban");
  if (timer.ends_at) return <RunningTimer timer={timer} />;
  return (
    <TimerFace left={timerLeft(timer, 0)}>
      <Pause className="size-3 shrink-0" aria-hidden="true" />
      <span className="sr-only">{t("card.time.paused")}</span>
    </TimerFace>
  );
}

/** План и факт: «2 ч 30 мин / 4 ч»; факт сверх плана — красным. */
function TrackingChip({ tracking }: { tracking: TimeTracking }) {
  const { plan_minutes: plan, fact_minutes: fact } = tracking;
  const over = overPlan(tracking);
  const t = useTranslations("kanban");
  const locale = useLocale();
  const span = (minutes: number) => formatSpan(locale, minutes * MINUTE_MS);
  const factOf = (chunks: ReactNode) => <span className={cn(over && "text-destructive")}>{chunks}</span>;
  return (
    <Chip>
      <Clock className="size-3 shrink-0" aria-hidden="true" />
      <span className="sr-only">{t("card.time.tracking")}</span>
      <span className="truncate tabular-nums">
        {plan === null
          ? span(fact ?? 0)
          : t.rich("card.time.factOfPlan", { spent: fact === null ? "—" : span(fact), plan: span(plan), fact: factOf })}
      </span>
      {over ? <span className="sr-only">{t("card.time.overPlan")}</span> : null}
    </Chip>
  );
}

/** Чипы времени, видимых на доске полей. */
export function TimeChips({ card, visible }: { card: Card; visible: Record<TimeStickerId, boolean> }) {
  const running = visible.stopwatch && card.stopwatch?.running_since ? card.stopwatch : null;
  return (
    <>
      {running ? <StopwatchChip stopwatch={running} /> : null}
      {visible.timer && card.timer ? <TimerChip timer={card.timer} /> : null}
      {visible.time_tracking && card.time_tracking ? <TrackingChip tracking={card.time_tracking} /> : null}
    </>
  );
}
