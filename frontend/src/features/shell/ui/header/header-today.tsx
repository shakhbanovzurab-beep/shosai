"use client";

import { Suspense, use, useDeferredValue } from "react";

import { useFormatter, useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";

import { useClock, useWeatherKey } from "../../model/use-clock";
import { loadTodayWeather } from "../../model/weather-loader";
import { WeatherIcon } from "./weather-icon";

const Divider = () => <span aria-hidden="true" className="h-4 w-px bg-border" />;

const weatherSkeleton = (
  <>
    <Divider />
    <Skeleton className="h-4 w-24" />
  </>
);

function WeatherReading({ weatherKey }: { weatherKey: string }) {
  const t = useTranslations("weather");
  const format = useFormatter();
  const result = use(loadTodayWeather(weatherKey));
  if (result.status === "error") return null;

  const { code, isDay, condition, unit, now, high, low, fallback } = result.weather;
  const withUnit = (value: number) => format.number(value, { style: "unit", unit, maximumFractionDigits: 0 });
  const place = fallback ? t("fallbackPlace") : null;
  const reading = {
    condition: t(`conditions.${condition}`),
    now: withUnit(now),
    high: withUnit(high),
    low: withUnit(low),
  };
  const summary = place ? t("summaryAt", { ...reading, place }) : t("summary", reading);

  return (
    <>
      <Divider />
      <div className="flex items-center gap-1.5" title={summary}>
        <span className="sr-only">{summary}</span>
        <WeatherIcon code={code} isDay={isDay} aria-hidden="true" className="size-4 text-muted-foreground" />
        <span aria-hidden="true" className="font-medium tabular-nums">
          {t("now", { value: now })}
        </span>
        <span aria-hidden="true" className="hidden text-muted-foreground tabular-nums lg:inline">
          {t("range", { high, low })}
        </span>
        {place ? (
          <span aria-hidden="true" className="hidden text-muted-foreground xl:inline">
            · {place}
          </span>
        ) : null}
      </div>
    </>
  );
}

function HeaderWeather() {
  // Deferred so a refresh keeps showing the last reading instead of falling back to the skeleton.
  const weatherKey = useDeferredValue(useWeatherKey());
  if (weatherKey === null) return weatherSkeleton;
  return (
    <Suspense fallback={weatherSkeleton}>
      <WeatherReading weatherKey={weatherKey} />
    </Suspense>
  );
}

/** Today's time and weather, centred in the dashboard header. */
export function HeaderToday() {
  const clock = useClock();

  return (
    <div className="flex items-center gap-3 text-sm">
      {clock === null ? (
        <Skeleton className="h-4 w-20" />
      ) : (
        <time dateTime={clock.iso} className="flex items-baseline gap-1.5 whitespace-nowrap">
          <span className="font-medium tabular-nums">{clock.time}</span>
          <span className="hidden text-muted-foreground lg:inline">{clock.date}</span>
        </time>
      )}
      <HeaderWeather />
    </div>
  );
}
