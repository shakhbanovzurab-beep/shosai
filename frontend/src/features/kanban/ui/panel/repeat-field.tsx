"use client";

import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { firstDue, nextDue, recurrenceFor, weekdaysFrom } from "../../domain/recurrence";
import { type Recurrence, WEEKDAYS, type Weekday } from "../../domain/tasks-contract";
import { useToday } from "../../model/board-hooks";

type Every = "never" | Recurrence["every"];
const EVERY: Every[] = ["never", "day", "week", "month"];
const MONTH_DAYS = Array.from({ length: 31 }, (_, i) => i + 1);
// 1 января 2024 года — понедельник: от него берутся названия дней недели на языке человека.
const MONDAY = Date.UTC(2024, 0, 1);

/** Дни недели в порядке, принятом в языке человека (неделя с понедельника или с воскресенья). */
function useWeekdays(): Weekday[] {
  const locale = useLocale();
  const info = (new Intl.Locale(locale) as Intl.Locale & { getWeekInfo?: () => { firstDay: number } }).getWeekInfo?.();
  return weekdaysFrom(info?.firstDay ?? 1);
}

/** Повтор: никогда, каждый день, по выбранным дням недели, раз в месяц — и когда будет следующая задача. */
export function RepeatField({
  value,
  dueOn,
  labelId,
  disabled,
  onChange,
}: {
  value: Recurrence | null;
  dueOn: string | null;
  labelId: string;
  disabled: boolean;
  onChange: (recurrence: Recurrence | null) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  const today = useToday();
  const weekdays = useWeekdays();
  const after = (rule: Recurrence) => (dueOn ? nextDue(rule, dueOn, today) : firstDue(rule, today));
  const next = value && today ? after(value) : null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={value?.every ?? "never"}
          disabled={disabled}
          onValueChange={(every) => onChange(recurrenceFor(every as Every, value, dueOn ?? today))}
        >
          <SelectTrigger size="sm" aria-labelledby={labelId} className="min-w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {EVERY.map((every) => (
                <SelectItem key={every} value={every}>
                  {t(`repeat.${every}`)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        {value?.every === "month" ? (
          <Select
            value={String(value.day)}
            disabled={disabled}
            onValueChange={(day) => onChange({ every: "month", day: Number(day) })}
          >
            <SelectTrigger size="sm" aria-label={t("repeat.onDay", { day: value.day })}>
              <SelectValue>{t("repeat.onDay", { day: value.day })}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {MONTH_DAYS.map((day) => (
                  <SelectItem key={day} value={String(day)}>
                    {format.number(day)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        ) : null}
        {next ? (
          <span className="text-muted-foreground text-xs">
            {t("repeat.next", {
              date: format.dateTime(new Date(next), {
                weekday: "short",
                month: "short",
                day: "numeric",
                timeZone: "UTC",
              }),
            })}
          </span>
        ) : null}
      </div>
      {value?.every === "week" ? (
        <ToggleGroup
          type="multiple"
          size="sm"
          variant="outline"
          disabled={disabled}
          aria-label={t("repeat.weekdays")}
          value={value.weekdays}
          // Неделя без дней не бывает: последний выбранный день снять нельзя.
          onValueChange={(days) =>
            days.length > 0 ? onChange({ every: "week", weekdays: days as Weekday[] }) : undefined
          }
          className="flex-wrap"
        >
          {weekdays.map((day) => (
            <ToggleGroupItem key={day} value={day} className="min-w-10">
              {format.dateTime(MONDAY + WEEKDAYS.indexOf(day) * 86_400_000, { weekday: "short", timeZone: "UTC" })}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : null}
    </div>
  );
}
