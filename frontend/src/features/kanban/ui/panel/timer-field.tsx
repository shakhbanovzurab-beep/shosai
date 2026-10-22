"use client";

import { cn } from "cn";
import { Pause, Play, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { formatClock } from "@/i18n/format-units";

import type { TaskDetail } from "../../domain/tasks-contract";
import { timerLeft } from "../../domain/time-rules";
import { useServerSecondWhile } from "../../model/server-clock";
import { TimerPicker } from "./timer-picker";
import { useClockActions } from "./use-panel-actions";

/**
 * Таймер в панели (KT-D3): сколько осталось с секундами, после нуля — «Время вышло» и перерасход; пауза и
 * продолжение, «Изменить» (задать заново) и «Убрать». Без таймера — только «Задать таймер».
 */
export function TimerField({ detail, labelId, disabled }: { detail: TaskDetail; labelId: string; disabled: boolean }) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const clocks = useClockActions(detail.id);
  const { timer } = detail;
  const running = Boolean(timer?.ends_at);
  const now = useServerSecondWhile(running);
  const set = (ms: number) => void clocks.setTimer(ms);
  if (!timer)
    return (
      <TimerPicker
        label={t("time.setTimer")}
        action="set-timer"
        describedBy={labelId}
        disabled={disabled}
        onPick={set}
      />
    );
  const left = timerLeft(timer, now);
  const up = left <= 0;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={cn("font-medium text-sm tabular-nums", up && "text-destructive")}>
        {up
          ? t("time.timeUp", { time: formatClock(locale, -left) })
          : t("time.left", { time: formatClock(locale, left) })}
        {running ? null : <span className="ms-1 font-normal text-muted-foreground">· {t("time.paused")}</span>}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        aria-describedby={labelId}
        data-clock-action="hold"
        onClick={() => void clocks.hold(running)}
      >
        {running ? <Pause data-icon="inline-start" /> : <Play data-icon="inline-start" />}
        {t(running ? "time.pause" : "time.resume")}
      </Button>
      <TimerPicker
        label={t("time.change")}
        action="change-timer"
        describedBy={labelId}
        disabled={disabled}
        onPick={set}
      />
      <Button
        variant="ghost"
        size="icon-sm"
        disabled={disabled}
        aria-label={t("time.removeTimer")}
        data-clock-action="remove-timer"
        onClick={() => void clocks.removeTimer()}
      >
        <X />
      </Button>
    </div>
  );
}
