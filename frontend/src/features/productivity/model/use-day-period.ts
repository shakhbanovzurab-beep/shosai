"use client";

import { useSyncExternalStore } from "react";

import { type DayPeriod, dayPeriod } from "../domain/days";

// Looked at once a minute: cheap, and right in time zones whose hours start at :30 or :45.
const subscribe = (onChange: () => void) => {
  const id = window.setInterval(onChange, 60_000);
  return () => window.clearInterval(id);
};
const getPeriod = () => dayPeriod(new Date().getHours());
const getServerPeriod = (): DayPeriod | null => null;

/** The part of the day on the viewer's own clock; null while server rendering, which can't know that clock. */
export const useDayPeriod = () => useSyncExternalStore<DayPeriod | null>(subscribe, getPeriod, getServerPeriod);
