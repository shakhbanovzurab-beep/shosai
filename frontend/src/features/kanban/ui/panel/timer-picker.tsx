"use client";

import { useId, useState } from "react";

import { Timer as TimerIcon } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field-text";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatSpan } from "@/i18n/format-units";

import { type DurationDraft, minutesFromInput } from "../../domain/duration-input";
import { TIMER_MAX_MS, TIMER_MIN_MS, TIMER_PRESETS_MS } from "../../domain/time-contract";
import { DurationInputs } from "./duration-inputs";

const MINUTE_MS = 60_000;

/** Своя длительность: часы и минуты, от минуты до года. */
function CustomLength({ onPick }: { onPick: (ms: number) => void }) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const labelId = useId();
  const errorId = useId();
  const [draft, setDraft] = useState<DurationDraft>({ hours: "", minutes: "" });
  const [invalid, setInvalid] = useState(false);
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const minutes = minutesFromInput(draft.hours, draft.minutes, locale, TIMER_MAX_MS / MINUTE_MS);
        if (minutes === null || minutes === undefined || minutes * MINUTE_MS < TIMER_MIN_MS) return setInvalid(true);
        onPick(minutes * MINUTE_MS);
      }}
    >
      <span id={labelId} className="font-medium text-xs">
        {t("time.custom")}
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <DurationInputs labelId={labelId} value={draft} onChange={setDraft} invalid={invalid} errorId={errorId} />
        <Button type="submit" size="sm">
          {t("time.startTimer")}
        </Button>
      </div>
      {invalid ? <FieldError id={errorId}>{t("time.lengthInvalid")}</FieldError> : null}
    </form>
  );
}

/** Выбор длительности таймера (KT-D3): готовые — полчаса, час, четыре часа, день, неделя — или своя. */
export function TimerPicker({
  label,
  action,
  describedBy,
  disabled,
  onPick,
}: {
  label: string;
  /** Метка кнопки для сценариев проверки: задать таймер или изменить. */
  action: "set-timer" | "change-timer";
  describedBy: string;
  disabled: boolean;
  onPick: (ms: number) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const pick = (ms: number) => {
    setOpen(false);
    onPick(ms);
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          aria-describedby={describedBy}
          data-clock-action={action}
        >
          <TimerIcon data-icon="inline-start" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(22rem,calc(100vw-2rem))] gap-3 p-3">
        <fieldset className="flex flex-wrap gap-1.5">
          <legend className="sr-only">{t("time.presets")}</legend>
          {TIMER_PRESETS_MS.map((ms) => (
            <Button
              key={ms}
              variant="secondary"
              size="sm"
              className="tabular-nums"
              data-timer-preset={ms}
              onClick={() => pick(ms)}
            >
              {formatSpan(locale, ms)}
            </Button>
          ))}
        </fieldset>
        <CustomLength onPick={pick} />
      </PopoverContent>
    </Popover>
  );
}
