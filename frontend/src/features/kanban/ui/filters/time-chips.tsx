"use client";

import { useTranslations } from "use-intl";

import {
  STOPWATCH_BUCKETS,
  type StopwatchBucket,
  TIMER_BUCKETS,
  type TimerBucket,
  TRACKING_BUCKETS,
  type TrackingBucket,
} from "../../domain/filter-contract";
import { setFilter } from "./filter-address";
import { FixedChip } from "./system-chips";
import { useActiveFilter } from "./use-visible-cards";

/* Фильтры полей времени (KT-D7): у каждого — три выбора, «или» внутри поля. */

export function StopwatchChip({ field }: { field: string }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  return (
    <FixedChip<StopwatchBucket>
      field={field}
      choices={STOPWATCH_BUCKETS.map((value) => ({ value, label: t(`stopwatch.${value}`) }))}
      selected={filter.stopwatch}
      onChange={(stopwatch) => setFilter((current) => ({ ...current, stopwatch }))}
    />
  );
}

export function TimerChip({ field }: { field: string }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  return (
    <FixedChip<TimerBucket>
      field={field}
      choices={TIMER_BUCKETS.map((value) => ({ value, label: t(`timer.${value}`) }))}
      selected={filter.timer}
      onChange={(timer) => setFilter((current) => ({ ...current, timer }))}
    />
  );
}

export function TrackingChip({ field }: { field: string }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  return (
    <FixedChip<TrackingBucket>
      field={field}
      choices={TRACKING_BUCKETS.map((value) => ({ value, label: t(`tracking.${value}`) }))}
      selected={filter.tracking}
      onChange={(tracking) => setFilter((current) => ({ ...current, tracking }))}
    />
  );
}
