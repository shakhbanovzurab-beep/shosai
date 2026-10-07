"use client";

import { useSyncExternalStore } from "react";

const MINUTE_MS = 60 * 1000;
const WEATHER_REFRESH_MS = 30 * 60 * 1000;

/** The interface language: what <html lang> says the frontend is written in, not the browser's preference. */
export const getUiLanguage = () => document.documentElement.lang || "en";

/** A store that ticks on each wall-clock boundary of `intervalMs`, and whenever <html lang> changes. */
const createTicker = (intervalMs: number) => (onChange: () => void) => {
  let timer = 0;
  const schedule = () => {
    timer = window.setTimeout(
      () => {
        onChange();
        schedule();
      },
      intervalMs - (Date.now() % intervalMs),
    );
  };
  schedule();
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
  return () => {
    window.clearTimeout(timer);
    observer.disconnect();
  };
};

const subscribeMinute = createTicker(MINUTE_MS);
const subscribeWeather = createTicker(WEATHER_REFRESH_MS);
const getServerSnapshot = () => null;

export type ClockReading = { iso: string; time: string; date: string };

let reading: (ClockReading & { key: string }) | null = null;

// Building an Intl.DateTimeFormat is expensive, so reuse one pair per language.
const TIME_OPTIONS: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
const DATE_OPTIONS: Intl.DateTimeFormatOptions = { weekday: "short", day: "numeric", month: "short" };
const formatters = new Map<string, { time: Intl.DateTimeFormat; date: Intl.DateTimeFormat }>();

const getFormatters = (language: string) => {
  let pair = formatters.get(language);
  if (!pair) {
    pair = {
      time: new Intl.DateTimeFormat(language, TIME_OPTIONS),
      date: new Intl.DateTimeFormat(language, DATE_OPTIONS),
    };
    formatters.set(language, pair);
  }
  return pair;
};

// Formatted once per minute in the interface language and the viewer's timezone, outside render.
const getClockSnapshot = (): ClockReading => {
  const language = getUiLanguage();
  const minute = Math.floor(Date.now() / MINUTE_MS);
  const key = `${minute}|${language}`;
  if (reading?.key !== key) {
    const ms = minute * MINUTE_MS;
    const format = getFormatters(language);
    reading = {
      key,
      iso: new Date(ms).toISOString(),
      time: format.time.format(ms),
      date: format.date.format(ms),
    };
  }
  return reading;
};

/** The current time, formatted for the viewer; `null` while server rendering so hydration never mismatches. */
export function useClock(): ClockReading | null {
  return useSyncExternalStore(subscribeMinute, getClockSnapshot, getServerSnapshot);
}

const getWeatherKey = () => `${Math.floor(Date.now() / WEATHER_REFRESH_MS)}|${getUiLanguage()}`;

/** Changes every 30 minutes or when <html lang> changes, to key weather loads; `null` while server rendering. */
export function useWeatherKey(): string | null {
  return useSyncExternalStore(subscribeWeather, getWeatherKey, getServerSnapshot);
}
