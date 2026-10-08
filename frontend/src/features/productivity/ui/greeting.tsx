"use client";

import { useTranslations } from "use-intl";

import { useDayPeriod } from "../model/use-day-period";

/**
 * "Good morning, Arham." The part of the day comes from the viewer's clock, so it is picked in the browser after
 * mount; the server renders a greeting that fits any hour. The name is the user's own.
 */
export function Greeting({ name }: { name: string }) {
  const t = useTranslations("productivity");
  const period = useDayPeriod();
  return (
    <h1 className="text-3xl text-foreground leading-none tracking-tight">
      {period === null ? t("greetingAnyTime", { name }) : t("greeting", { period, name })}
    </h1>
  );
}
