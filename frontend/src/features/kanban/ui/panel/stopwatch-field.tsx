"use client";

import { useState } from "react";

import { Play, RotateCcw, Square } from "lucide-react";
import { toast } from "sonner";
import { useLocale, useTranslations } from "use-intl";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { formatClock, formatSpan } from "@/i18n/format-units";

import type { TaskDetail } from "../../domain/tasks-contract";
import type { Stopwatch } from "../../domain/time-contract";
import { runningSpan, stopwatchElapsed } from "../../domain/time-rules";
import { useBoardSelector } from "../../model/board-hooks";
import { useServerSecondWhile } from "../../model/server-clock";
import { useClockActions } from "./use-panel-actions";

const MINUTE_MS = 60_000;

/** Время задачи по колонкам этой доски, в их порядке; идущий отрезок — в колонке, где задача сейчас. */
function ColumnTimes({ stopwatch, columnId, now }: { stopwatch: Stopwatch; columnId: string | null; now: number }) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const columns = useBoardSelector((s) => s.columnOrder);
  const titles = useBoardSelector((s) => s.columns);
  const rows = columns
    .map((id) => ({ id, ms: (stopwatch.by_column[id] ?? 0) + (id === columnId ? runningSpan(stopwatch, now) : 0) }))
    .filter((row) => row.ms > 0);
  if (rows.length === 0) return null;
  return (
    <figure>
      <figcaption className="sr-only">{t("time.perColumn")}</figcaption>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground text-xs">
        {rows.map((row) => (
          <div key={row.id} className="contents">
            <dt dir="auto" className="truncate">
              {titles[row.id]?.title}
            </dt>
            <dd className="tabular-nums">{formatSpan(locale, row.ms)}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}

/** «Сбросить» с подтверждением: время секундомера и по колонкам уходит совсем. */
function ResetButton({ elapsed, describedBy, onReset }: { elapsed: string; describedBy: string; onReset: () => void }) {
  const t = useTranslations("kanbanPanel");
  const tc = useTranslations("common");
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        aria-describedby={describedBy}
        data-clock-action="reset"
        onClick={() => setOpen(true)}
      >
        <RotateCcw data-icon="inline-start" />
        {t("time.reset")}
      </Button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("time.resetTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("time.resetText", { time: elapsed })}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc("actions.cancel")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" data-clock-action="confirm-reset" onClick={onReset}>
              {t("time.reset")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

/**
 * Секундомер в панели (KT-D1): время с секундами, «Запустить» и «Остановить», «Сбросить» с подтверждением, время по
 * колонкам, если доска его считает. Остановка предлагает прибавить отрезок к факту, когда доска ведёт учёт (KT-D4).
 */
export function StopwatchField({
  detail,
  labelId,
  disabled,
  offerFact,
}: {
  detail: TaskDetail;
  labelId: string;
  disabled: boolean;
  offerFact: boolean;
}) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const clocks = useClockActions(detail.id);
  const { stopwatch } = detail;
  const running = Boolean(stopwatch?.running_since);
  const now = useServerSecondWhile(running);
  const perColumn = useBoardSelector((s) => s.stickers.find((x) => x.id === "stopwatch")?.automations?.restart_on_move);
  const elapsed = stopwatch ? formatClock(locale, stopwatchElapsed(stopwatch, now)) : null;
  const stop = async () => {
    const minutes = Math.floor(((await clocks.stop()) ?? 0) / MINUTE_MS);
    if (!offerFact || minutes < 1) return;
    const time = formatSpan(locale, minutes * MINUTE_MS);
    toast(t("time.stopped", { time }), {
      action: { label: t("time.addToFact", { time }), onClick: () => void clocks.addToFact(minutes) },
    });
  };
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-16 font-medium text-sm tabular-nums">{elapsed ?? t("time.notStarted")}</span>
        {running ? (
          <Button
            variant="outline"
            size="sm"
            disabled={disabled}
            aria-describedby={labelId}
            data-clock-action="stop"
            onClick={() => void stop()}
          >
            <Square data-icon="inline-start" />
            {t("time.stop")}
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            disabled={disabled}
            aria-describedby={labelId}
            data-clock-action="start"
            onClick={() => void clocks.start()}
          >
            <Play data-icon="inline-start" />
            {t("time.start")}
          </Button>
        )}
        {elapsed && !disabled ? (
          <ResetButton elapsed={elapsed} describedBy={labelId} onReset={() => void clocks.reset()} />
        ) : null}
      </div>
      {perColumn && stopwatch ? (
        <ColumnTimes stopwatch={stopwatch} columnId={detail.placement?.column_id ?? null} now={now} />
      ) : null}
    </div>
  );
}
