"use client";

import { useSyncExternalStore } from "react";

import { hourIn } from "@/i18n/calendar-days";
import { cabinetTimeZone } from "@/i18n/time-zone";

import { type DayPeriod, dayPeriod } from "../domain/days";

// Looked at once a minute: cheap, and right in time zones whose hours start at :30 or :45.
const subscribe = (onChange: () => void) => {
  const id = window.setInterval(onChange, 60_000);
  return () => window.clearInterval(id);
};
const getPeriod = () => dayPeriod(hourIn(Date.now(), cabinetTimeZone()));
const getServerPeriod = (): DayPeriod | null => null;

/** Часть дня на часах человека в поясе кабинета; null при серверной отрисовке, которая этих часов не знает. */
export const useDayPeriod = () => useSyncExternalStore<DayPeriod | null>(subscribe, getPeriod, getServerPeriod);
