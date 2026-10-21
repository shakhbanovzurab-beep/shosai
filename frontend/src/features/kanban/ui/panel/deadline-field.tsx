"use client";

import { Suspense, useState } from "react";

import { CalendarDays } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { useDirection } from "@/components/ui/direction";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useDateFnsLocale } from "@/i18n/use-date-fns-locale";

import type { TaskPatch } from "../../domain/tasks-contract";
import { dayKeyOf, localDay } from "./day-keys";
import { useValueLabel } from "./value-label";

type Dates = { starts_on: string | null; due_on: string | null };
export type DeadlineMode = "day" | "range";
type Mode = DeadlineMode;
const DAY = { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" } as const;

/** Календарь дня или диапазона: выбор сразу уходит в задачу; диапазон — когда выбраны оба края. */
function DatesCalendar({ dates, mode, onPick }: { dates: Dates; mode: Mode; onPick: (patch: TaskPatch) => void }) {
  const locale = useDateFnsLocale();
  const dir = useDirection();
  const due = dates.due_on ? localDay(dates.due_on) : undefined;
  if (mode === "day")
    return (
      <Calendar
        mode="single"
        locale={locale}
        dir={dir}
        selected={due}
        defaultMonth={due}
        onSelect={(day) => (day ? onPick({ due_on: dayKeyOf(day), starts_on: null }) : undefined)}
      />
    );
  const from = dates.starts_on ? localDay(dates.starts_on) : due;
  return (
    <Calendar
      mode="range"
      locale={locale}
      dir={dir}
      selected={{ from, to: due }}
      defaultMonth={from}
      onSelect={(range) =>
        range?.from && range.to ? onPick({ starts_on: dayKeyOf(range.from), due_on: dayKeyOf(range.to) }) : undefined
      }
    />
  );
}

/** Срок: день или диапазон, со сбросом. Пока срока нет — «Не задан». */
export function DeadlineField({
  dates,
  labelId,
  disabled,
  modes,
  onChange,
}: {
  dates: Dates;
  labelId: string;
  disabled: boolean;
  /** Какие виды срока доступны: у задачи Jira — только день (KG-D8). */
  modes: readonly DeadlineMode[];
  onChange: (patch: TaskPatch) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const valueLabel = useValueLabel(labelId);
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>(dates.starts_on ? "range" : "day");
  const due = dates.due_on ? new Date(dates.due_on) : null;
  let text = t("notSet");
  if (due)
    text = dates.starts_on ? format.dateTimeRange(new Date(dates.starts_on), due, DAY) : format.dateTime(due, DAY);
  const pick = (patch: TaskPatch) => {
    setOpen(false);
    onChange(patch);
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" disabled={disabled} {...valueLabel} className="font-normal">
          <CalendarDays data-icon="inline-start" />
          {text}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="flex w-auto flex-col gap-2 p-2">
        {modes.length > 1 ? (
          <ToggleGroup
            type="single"
            size="sm"
            variant="outline"
            value={mode}
            onValueChange={(v) => (v ? setMode(v as Mode) : undefined)}
          >
            <ToggleGroupItem value="day">{t("due.day")}</ToggleGroupItem>
            <ToggleGroupItem value="range">{t("due.range")}</ToggleGroupItem>
          </ToggleGroup>
        ) : null}
        <Suspense fallback={<Skeleton className="h-72 w-64" />}>
          <DatesCalendar dates={dates} mode={modes.includes(mode) ? mode : "day"} onPick={pick} />
        </Suspense>
        {due ? (
          <Button variant="ghost" size="sm" onClick={() => pick({ due_on: null, starts_on: null })}>
            {t("due.clear")}
          </Button>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
