"use client";

import { useId, useState } from "react";

import { useLocale, useTranslations } from "use-intl";

import { FieldError } from "@/components/ui/field-text";

import { type DurationDraft, draftOf, minutesFromInput } from "../../domain/duration-input";
import type { TaskDetail } from "../../domain/tasks-contract";
import { type TimeTracking, TRACKED_MINUTES_MAX } from "../../domain/time-contract";
import { overPlan } from "../../domain/time-rules";
import { DurationInputs } from "./duration-inputs";
import { useClockActions } from "./use-panel-actions";

/**
 * План или факт: пока человек правит, поля держат набранное; сохраняется по Enter или когда фокус уходит из пары,
 * Esc возвращает сохранённое. Не правит — поля показывают то, что у задачи сейчас (и прибавку к факту из тоста).
 */
function MinutesInput({
  label,
  minutes,
  disabled,
  onCommit,
}: {
  label: string;
  minutes: number | null;
  disabled: boolean;
  onCommit: (minutes: number | null) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const labelId = useId();
  const [draft, setDraft] = useState<DurationDraft | null>(null);
  const [invalid, setInvalid] = useState(false);
  const commit = () => {
    if (!draft) return;
    const next = minutesFromInput(draft.hours, draft.minutes, locale, TRACKED_MINUTES_MAX);
    if (next === undefined) return setInvalid(true);
    setDraft(null);
    setInvalid(false);
    if (next !== minutes) onCommit(next);
  };
  return (
    <div
      className="flex flex-col gap-1"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) commit();
      }}
    >
      <div className="flex items-center gap-2">
        <span id={labelId} className="w-12 text-muted-foreground text-xs">
          {label}
        </span>
        <DurationInputs
          labelId={labelId}
          value={draft ?? draftOf(minutes, locale)}
          disabled={disabled}
          invalid={invalid}
          onChange={setDraft}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
            if (event.key === "Escape" && draft) {
              setDraft(null);
              setInvalid(false);
            }
          }}
        />
      </div>
      {invalid ? <FieldError>{t("time.durationInvalid")}</FieldError> : null}
    </div>
  );
}

/** План и факт задачи (KT-D4); факт сверх плана — заметно и словами. */
export function TrackingField({ detail, disabled }: { detail: TaskDetail; disabled: boolean }) {
  const t = useTranslations("kanbanPanel");
  const clocks = useClockActions(detail.id);
  const tracking: TimeTracking = detail.time_tracking ?? { plan_minutes: null, fact_minutes: null };
  return (
    <div className="flex flex-col gap-2">
      <MinutesInput
        label={t("time.plan")}
        minutes={tracking.plan_minutes}
        disabled={disabled}
        onCommit={(plan_minutes) => void clocks.setTracking({ plan_minutes })}
      />
      <MinutesInput
        label={t("time.fact")}
        minutes={tracking.fact_minutes}
        disabled={disabled}
        onCommit={(fact_minutes) => void clocks.setTracking({ fact_minutes })}
      />
      {overPlan(tracking) ? <p className="text-destructive text-xs">{t("time.overPlan")}</p> : null}
    </div>
  );
}
