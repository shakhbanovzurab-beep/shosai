"use client";

import { useId } from "react";

import { useTranslations } from "use-intl";

import type { TaskDetail } from "../../domain/tasks-contract";
import { useBoardStickers } from "../../model/board-hooks";
import { FieldRow } from "./field-row";
import { StopwatchField } from "./stopwatch-field";
import { TimerField } from "./timer-field";
import { TrackingField } from "./tracking-field";

/**
 * Строки времени в панели (ADR 0061): поле видно, когда доска показывает его на карточках или у задачи уже есть
 * его значение, — иначе панель не растёт тремя пустыми строками. У задачи Jira их нет (KG-D8).
 */
export function TimeRows({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  const t = useTranslations("kanbanPanel");
  const stickers = useBoardStickers();
  const ids = { stopwatch: useId(), timer: useId(), tracking: useId() };
  if (detail.jira) return null;
  const shown = (id: string) => stickers.find((sticker) => sticker.id === id)?.visible ?? false;
  return (
    <>
      {shown("stopwatch") || detail.stopwatch ? (
        <FieldRow label={t("fields.stopwatch")} labelId={ids.stopwatch}>
          <StopwatchField
            detail={detail}
            labelId={ids.stopwatch}
            disabled={!editable}
            offerFact={shown("time_tracking")}
          />
        </FieldRow>
      ) : null}
      {shown("timer") || detail.timer ? (
        <FieldRow label={t("fields.timer")} labelId={ids.timer}>
          <TimerField detail={detail} labelId={ids.timer} disabled={!editable} />
        </FieldRow>
      ) : null}
      {shown("time_tracking") || detail.time_tracking ? (
        <FieldRow label={t("fields.time_tracking")} labelId={ids.tracking}>
          <TrackingField detail={detail} disabled={!editable} />
        </FieldRow>
      ) : null}
    </>
  );
}
