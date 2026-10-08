"use client";

import {
  CalendarClock,
  CalendarDays,
  CalendarPlus,
  CalendarRange,
  ClipboardCopy,
  Copy,
  Pencil,
  Redo2,
  Trash2,
  Undo2,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { contextKit as K } from "@/components/menu-kit";
import { ContextMenuLabel } from "@/components/ui/context-menu-items";

import type { CalendarEvent, EventSlot } from "../domain/calendar-event";
import type { CalendarActions } from "../model/use-calendar-events";
import { useEventWhen } from "../model/use-event-when";

export function EventMenuItems({ event, actions }: { event: CalendarEvent; actions: CalendarActions }) {
  const t = useTranslations("calendar");
  const common = useTranslations("common");
  const when = useEventWhen();
  return (
    <>
      <ContextMenuLabel className="truncate">
        <span dir="auto">{event.title}</span>
        <span className="block font-normal text-muted-foreground text-xs">{when.short(event.start, event.allDay)}</span>
      </ContextMenuLabel>
      <K.Separator />
      <K.Group>
        <K.Item onSelect={() => actions.rename(event.id)}>
          <Pencil />
          {common("actions.renameMenu")}
        </K.Item>
        <K.Sub>
          <K.SubTrigger>
            <CalendarClock />
            {t("eventMenu.reschedule")}
          </K.SubTrigger>
          <K.SubContent className="w-44">
            <K.Item onSelect={() => actions.reschedule(event.id, -1)}>
              <Undo2 className="rtl:-scale-x-100" />
              {t("eventMenu.dayEarlier")}
            </K.Item>
            <K.Item onSelect={() => actions.reschedule(event.id, 1)}>
              <Redo2 className="rtl:-scale-x-100" />
              {t("eventMenu.dayLater")}
            </K.Item>
            <K.Item onSelect={() => actions.reschedule(event.id, 7)}>
              <CalendarRange />
              {t("eventMenu.nextWeek")}
            </K.Item>
            <K.Separator />
            <K.Item onSelect={() => actions.moveToToday(event.id)}>
              <CalendarDays />
              {t("eventMenu.moveToToday")}
            </K.Item>
          </K.SubContent>
        </K.Sub>
        <K.Item onSelect={() => actions.duplicate(event.id)}>
          <Copy />
          {common("actions.duplicate")}
        </K.Item>
        <K.Item onSelect={() => actions.copyDetails(event.id)}>
          <ClipboardCopy />
          {t("eventMenu.copyDetails")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.Item variant="destructive" onSelect={() => actions.remove(event.id)}>
          <Trash2 />
          {t("eventMenu.delete")}
        </K.Item>
      </K.Group>
    </>
  );
}

type DayMenuItemsProps = {
  slot: EventSlot;
  actions: CalendarActions;
  openDay: (date: Date, view: "timeGridDay" | "timeGridWeek") => void;
};

export function DayMenuItems({ slot, actions, openDay }: DayMenuItemsProps) {
  const t = useTranslations("calendar");
  const when = useEventWhen();
  return (
    <>
      <ContextMenuLabel>{when.long(slot.date, slot.allDay)}</ContextMenuLabel>
      <K.Separator />
      <K.Group>
        <K.Item onSelect={() => actions.add(slot)}>
          <CalendarPlus />
          {slot.allDay ? t("dayMenu.newAllDay") : t("dayMenu.newAt", { time: when.time(slot.date) })}
        </K.Item>
        {slot.allDay ? null : (
          <K.Item onSelect={() => actions.add({ date: slot.date, allDay: true })}>
            <CalendarPlus />
            {t("dayMenu.newAllDay")}
          </K.Item>
        )}
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.Item onSelect={() => openDay(slot.date, "timeGridDay")}>
          <CalendarDays />
          {t("dayMenu.openDay")}
        </K.Item>
        <K.Item onSelect={() => openDay(slot.date, "timeGridWeek")}>
          <CalendarRange />
          {t("dayMenu.openWeek")}
        </K.Item>
      </K.Group>
    </>
  );
}
