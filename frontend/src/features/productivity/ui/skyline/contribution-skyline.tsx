"use client";

import * as React from "react";

import { cn } from "cn";
import { useLocale, useTranslations } from "next-intl";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { type ContributionDay, dayMs } from "../../domain/skyline/contributions";
import { createFormatters, statBlocks } from "../../domain/skyline/format";
import { buildModel } from "../../domain/skyline/stats";
import { SkylineLegend } from "./skyline-legend";
import { statViews } from "./skyline-stat-views";
import { SkylineCornerStats, SkylineStatsRow } from "./skyline-stats";
import { SkylineTooltip } from "./skyline-tooltip";
import { SkylineViewToggle } from "./skyline-view-toggle";
import { type SkylineView, useSkylineEngine } from "./use-skyline-engine";

export type ContributionSkylineProps = {
  /** Tasks done per day, `YYYY-MM-DD`. Repeated dates add up. Omit for a generated sample year. */
  data?: ContributionDay[];
  /** Last day shown. Defaults to the latest date in `data`, or today. */
  endDate?: string | Date;
  /** Starting view. The 3D view rises out of the flat one when it first scrolls into sight. */
  defaultView?: SkylineView;
  /** Heading. Defaults to "{total} completed tasks in the past year". */
  title?: React.ReactNode;
  /** Multiplies bar heights in 3D. */
  heightScale?: number;
  /** Morph length, ms. */
  duration?: number;
  /** 0 puts Sunday on the top row, 1 puts Monday there. */
  weekStart?: 0 | 1;
  /** Seed for the generated sample year. */
  seed?: number;
  onCellClick?: (day: ContributionDay) => void;
  className?: string;
};

/**
 * A year of completed tasks as a heat map that folds up into an isometric skyline and back.
 * Coloured from the theme's primary token, so it follows every preset and mode. Words, month and weekday
 * names, numbers and dates are in the interface language.
 */
export function ContributionSkyline({
  data,
  endDate,
  defaultView = "2d",
  title,
  heightScale = 1,
  duration = 1300,
  weekStart = 0,
  seed = 7,
  onCellClick,
  className,
}: ContributionSkylineProps) {
  const t = useTranslations("productivitySkyline");
  const locale = useLocale();
  const endKey = endDate == null ? null : dayMs(endDate);
  const model = React.useMemo(
    () => buildModel(data, endKey, seed, weekStart, locale),
    [data, endKey, seed, weekStart, locale],
  );
  const [view, setView] = React.useState<SkylineView>(defaultView);

  const fmt = React.useMemo(() => createFormatters(locale), [locale]);
  const describe = (i: number) => {
    const c = model.cells[i];
    return c ? t("day", { count: c.count, date: fmt.long(c.date) }) : "";
  };

  const rootRef = React.useRef<HTMLDivElement>(null);
  const stageRef = React.useRef<HTMLDivElement>(null);
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const tipRef = React.useRef<HTMLDivElement>(null);
  const { width, active, announce, swatches, legendLevel, setLegendLevel } = useSkylineEngine({
    refs: { rootRef, stageRef, canvasRef, tipRef },
    model,
    view,
    duration,
    heightScale,
    orbit: true,
    locale,
    onCellClick,
    describe,
  });

  const { stats } = model;
  const blocks = statViews(statBlocks(stats, fmt), t, fmt);
  const is3d = view === "3d";
  const corners = width >= 560;
  const bigSize = Math.round(Math.max(30, Math.min(56, width * 0.058)));
  const activeCell = active >= 0 ? model.cells[active] : undefined;
  const span = {
    count: stats.total,
    from: stats.first ? fmt.dayWithYear(stats.first) : "—",
    to: stats.last ? fmt.dayWithYear(stats.last) : "—",
  };

  return (
    <Card ref={rootRef} className={cn("shadow-xs", className)}>
      <CardHeader>
        <CardTitle className="font-normal">
          {title ??
            t.rich("title", {
              count: stats.total,
              b: (chunks) => <span className="font-semibold tabular-nums">{chunks}</span>,
            })}
        </CardTitle>
        <CardAction>
          <SkylineViewToggle view={view} onChange={setView} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="relative rounded-lg border">
          {/*
           * The chart keeps time running left to right in every language, as the product's other charts do: the
           * isometric camera, the side faces' shading, the orbit drag and the empty corners the 3D stats settle
           * into are all built on that orientation, and the arrow keys move the way the cells are drawn
           * (ArrowLeft is an earlier week). Its words still follow the page: the tooltip's and the corner stats'
           * text, and everything outside this frame (stats row, hint, legend).
           */}
          <div dir="ltr" className="relative px-3 pt-3 sm:px-4 sm:pt-4">
            <div
              ref={stageRef}
              className="relative w-full overflow-hidden rounded-md outline-ring outline-offset-4 has-[:focus-visible]:outline-2"
              style={{ height: 150 }}
            >
              <canvas
                ref={canvasRef}
                tabIndex={0}
                role="img"
                aria-label={is3d ? t("chart.skyline", span) : t("chart.flat", span)}
                className="absolute start-0 top-0 block max-w-none outline-none"
                style={{ touchAction: is3d ? "pan-y" : "auto" }}
              />
              {corners ? <SkylineCornerStats stats={blocks} visible={is3d} size={bigSize} duration={duration} /> : null}
            </div>
            <SkylineTooltip ref={tipRef} cell={activeCell} fmt={fmt} />
          </div>
          <div className="h-3 sm:h-4" />
          {!is3d || !corners ? <SkylineStatsRow stats={blocks} /> : null}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <p className="text-muted-foreground text-xs">{is3d ? t("hint.skyline") : t("hint.flat")}</p>
          <SkylineLegend swatches={swatches} activeLevel={legendLevel} onLevelChange={setLegendLevel} />
        </div>
        <p aria-live="polite" className="sr-only">
          {announce}
        </p>
      </CardContent>
    </Card>
  );
}
