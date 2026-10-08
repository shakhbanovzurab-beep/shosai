"use client";

import { useEffect } from "react";

import { cn } from "cn";
import { Bell, BellOff, Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { formatClock, isRunning, phaseMs, presetOf } from "../domain/focus/timer";
import { focusActions, useFocusTimer } from "../model/focus-store";
import { useTimeLeft } from "../model/use-time-left";
import { presetName } from "../model/words";
import { FocusRhythmPicker } from "./focus-rhythm-picker";
import { FocusRing } from "./focus-ring";

/** Sessions done before the next long break, as dots; the count is in the text beside it for screen readers. */
function CycleDots({ done, every }: { done: number; every: number }) {
  const t = useTranslations("productivityFocus");
  const slots = Array.from({ length: every }, (_, i) => ({ slot: `slot-${i + 1}`, filled: i < done }));
  return (
    <span className="flex items-center gap-1.5">
      {slots.map(({ slot, filled }) => (
        <span
          key={slot}
          aria-hidden="true"
          className={cn("size-1.5 rounded-full", filled ? "bg-primary" : "bg-muted")}
        />
      ))}
      <span className="sr-only">{t("cycle", { done, every })}</span>
    </span>
  );
}

/** Shows the time left in the tab title while the timer runs, so it's visible from other tabs. */
function useTitle(text: string | null) {
  useEffect(() => {
    if (!text) return;
    const original = document.title;
    document.title = text;
    return () => {
      document.title = original;
    };
  }, [text]);
}

/** A focus timer with proven rhythms: Pomodoro, 50/10, 52/17 and 90-minute deep work. */
export function FocusCard() {
  const t = useTranslations("productivityFocus");
  const { timer, sound } = useFocusTimer();
  const running = isRunning(timer);
  const left = useTimeLeft(timer);
  const preset = presetOf(timer.presetId);
  const total = phaseMs(preset, timer.phase);
  // A countdown ("25:00"), not a word: the same in every language.
  const clock = formatClock(left);
  const phase = t(`phase.${timer.phase}`);
  const onBreak = timer.phase !== "focus";
  const started = running || timer.remainingMs < total;

  // The phase ran out (also while the page was closed): move on to the next one.
  useEffect(() => {
    if (running && left === 0) focusActions.finish(t);
  }, [running, left, t]);
  useTitle(running ? t("tabTitle", { clock, phase }) : null);

  let startLabel = t("start");
  if (running) startLabel = t("pause");
  else if (started) startLabel = t("resume");

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardAction>
          <Button
            variant="ghost"
            size="icon-sm"
            className="text-muted-foreground"
            aria-pressed={sound}
            aria-label={t("sound.label")}
            title={sound ? t("sound.on") : t("sound.off")}
            onClick={focusActions.toggleSound}
          >
            {sound ? <Bell /> : <BellOff />}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-4">
        <FocusRhythmPicker value={timer.presetId} disabled={running} />

        <FocusRing progress={total === 0 ? 0 : 1 - left / total} onBreak={onBreak}>
          <span role="timer" className="font-medium text-4xl tabular-nums tracking-tight">
            {clock}
          </span>
          <span className={cn("text-xs", onBreak ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}>
            {phase}
          </span>
        </FocusRing>

        {/* Media-style controls (restart, play, skip) keep their shapes in right-to-left, as players do. */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("restart")}
            disabled={!started}
            onClick={focusActions.reset}
          >
            <RotateCcw />
          </Button>
          <Button className="min-w-28" onClick={focusActions.toggle}>
            {running ? <Pause data-icon="inline-start" /> : <Play data-icon="inline-start" />}
            {startLabel}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={onBreak ? t("skipBreak") : t("skipToBreak")}
            onClick={focusActions.skip}
          >
            <SkipForward />
          </Button>
        </div>

        <div className="flex w-full items-center justify-between gap-2 text-muted-foreground text-xs">
          {preset.longEvery > 0 ? (
            <CycleDots done={timer.cycleDone % preset.longEvery} every={preset.longEvery} />
          ) : (
            <span>{presetName(t, preset)}</span>
          )}
          <span className="tabular-nums">{t("doneToday", { count: timer.doneToday })}</span>
        </div>
        <p aria-live="polite" className="sr-only">
          {t("announce", { phase, clock: formatClock(total) })}
        </p>
      </CardContent>
    </Card>
  );
}
