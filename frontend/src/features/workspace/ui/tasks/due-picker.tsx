"use client";

import { Suspense, useState } from "react";

import { parseISO } from "date-fns";
import { CalendarClock } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { useDirection } from "@/components/ui/direction";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useDateFnsLocale } from "@/i18n/use-date-fns-locale";

import { type DueTone, dayKey } from "../../domain/format";
import { useDueWords } from "./use-due-words";

const TONE_VARIANT: Record<DueTone, "destructive" | "secondary" | "outline"> = {
  overdue: "destructive",
  today: "secondary",
  soon: "secondary",
  later: "outline",
};

/** The month grid in the interface language and direction; its locale loads on first use. */
function DueCalendar({
  dueOn,
  now,
  onPick,
}: {
  dueOn: string | null;
  now: number;
  onPick: (day: string | null) => void;
}) {
  const locale = useDateFnsLocale();
  const dir = useDirection();
  return (
    <Calendar
      mode="single"
      locale={locale}
      dir={dir}
      selected={dueOn ? parseISO(dueOn) : undefined}
      onSelect={(day) => onPick(day ? dayKey(day.getTime()) : null)}
      defaultMonth={dueOn ? parseISO(dueOn) : new Date(now)}
    />
  );
}

/** The due date as a chip; with `onChange` the chip opens a calendar to reschedule or clear it. */
export function DuePicker({
  dueOn,
  now,
  done,
  onChange,
}: {
  dueOn: string | null;
  now: number;
  done: boolean;
  onChange?: (dueOn: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const t = useTranslations("workspaceTasks.due");
  const words = useDueWords();
  const label = words.label(dueOn, now);
  const variant = label && !done ? TONE_VARIANT[label.tone] : "outline";
  let text = t("none");
  if (label && dueOn) text = done ? words.was(dueOn) : label.text;

  if (!onChange)
    return label ? (
      <Badge variant={variant} className="font-normal">
        {text}
      </Badge>
    ) : null;

  const pick = (next: string | null) => {
    setOpen(false);
    if (next !== dueOn) onChange(next);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="xs"
          aria-label={t("change", { due: text })}
          className={label ? "p-0 hover:bg-transparent" : "text-muted-foreground"}
        >
          {label ? (
            <Badge variant={variant} className="cursor-pointer font-normal">
              {text}
            </Badge>
          ) : (
            <>
              <CalendarClock data-icon="inline-start" />
              {t("add")}
            </>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-auto p-0">
        <Suspense fallback={<Skeleton className="m-3 h-64 w-60" />}>
          <DueCalendar dueOn={dueOn} now={now} onPick={pick} />
        </Suspense>
        {dueOn ? (
          <div className="border-t p-2">
            <Button variant="ghost" size="sm" className="w-full" onClick={() => pick(null)}>
              {t("clear")}
            </Button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
