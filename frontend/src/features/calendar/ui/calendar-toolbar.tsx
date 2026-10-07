"use client";

import { useState } from "react";

import type { CalendarController } from "@fullcalendar/react";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { VIEWS } from "./calendar-views";

const CALENDARS = ["all", "work", "personal", "team", "focus"] as const;

type CalendarToolbarProps = {
  controller: CalendarController;
  /** The visible period, already in the interface language ("June 2026"). */
  title: string;
  days: number;
  eventCount: number;
  onAdd: () => void;
};

/** The period on show with its counts, then the calendar filter, navigation, view switch and "Add event". */
export function CalendarToolbar({ controller, title, days, eventCount, onAdd }: CalendarToolbarProps) {
  const t = useTranslations("calendar");
  const [selectedCalendar, setSelectedCalendar] = useState<string>(CALENDARS[0]);

  return (
    <div className="flex flex-col gap-4 border-b bg-sidebar p-4 text-sidebar-foreground lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 shrink-0 flex-col gap-1">
        <div className="font-medium text-lg leading-none">{title}</div>
        <p className="text-muted-foreground text-sm">{t("summary", { days, events: eventCount })}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={selectedCalendar} onValueChange={setSelectedCalendar}>
          <SelectTrigger className="w-full sm:w-44" aria-label={t("calendars.label")}>
            <CalendarIcon />
            <SelectValue />
          </SelectTrigger>
          <SelectContent position="popper">
            <SelectGroup>
              {CALENDARS.map((key) => (
                <SelectItem key={key} value={key}>
                  {t(`calendars.${key}`)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <ButtonGroup>
          <Button size="icon" variant="outline" onClick={() => controller.prev()} aria-label={t("previous")}>
            <ChevronLeft className="rtl:-scale-x-100" />
          </Button>
          <Button variant="outline" onClick={() => controller.today()}>
            {t("today")}
          </Button>
          <Button size="icon" variant="outline" onClick={() => controller.next()} aria-label={t("next")}>
            <ChevronRight className="rtl:-scale-x-100" />
          </Button>
        </ButtonGroup>
        <Select value={controller.view?.type ?? VIEWS[0]} onValueChange={(value) => controller.changeView(value)}>
          <SelectTrigger aria-label={t("views.label")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="end">
            <SelectGroup>
              {VIEWS.map((view) => (
                <SelectItem key={view} value={view}>
                  {t(`views.${view}`)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button onClick={onAdd}>
          <Plus />
          {t("addEvent")}
        </Button>
      </div>
    </div>
  );
}
