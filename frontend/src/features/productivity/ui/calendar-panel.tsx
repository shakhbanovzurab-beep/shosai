"use client";

import * as React from "react";

import { startOfMonth, startOfToday } from "date-fns";

import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent } from "@/components/ui/card";
import { useDirection } from "@/components/ui/direction";
import { Skeleton } from "@/components/ui/skeleton";
import { useDateFnsLocale } from "@/i18n/use-date-fns-locale";

const SAMPLE_DAY = new Date(Date.UTC(2026, 0, 7));

/**
 * Weekday headers: the language's short names, or its narrow ones where short names don't fit a day column
 * (Arabic "أربعاء" becomes "ر").
 */
function weekdayFormatter(code: string) {
  const short = new Intl.DateTimeFormat(code, { weekday: "short" });
  const fits = short.format(SAMPLE_DAY).length <= 4;
  const format = fits ? short : new Intl.DateTimeFormat(code, { weekday: "narrow" });
  return (date: Date) => format.format(date);
}

/** The month in the interface language: its names, its first day of the week and its direction. */
function MonthCalendar() {
  const locale = useDateFnsLocale();
  const dir = useDirection();
  const today = startOfToday();
  const [date, setDate] = React.useState<Date | undefined>(today);
  const [currentMonth, setCurrentMonth] = React.useState<Date>(() => startOfMonth(today));

  return (
    <Calendar
      mode="single"
      selected={date}
      onSelect={setDate}
      month={currentMonth}
      onMonthChange={setCurrentMonth}
      fixedWeeks
      locale={locale}
      formatters={{ formatWeekdayName: weekdayFormatter(locale.code) }}
      dir={dir}
      className="w-full p-0"
    />
  );
}

export function CalendarPanel() {
  return (
    <Card className="w-full" size="sm">
      <CardContent>
        {/* The language's date-fns locale loads on first use. */}
        <React.Suspense fallback={<Skeleton className="aspect-4/5 w-full" />}>
          <MonthCalendar />
        </React.Suspense>
      </CardContent>
    </Card>
  );
}
