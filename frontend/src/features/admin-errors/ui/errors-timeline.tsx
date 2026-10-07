"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

import type { IssuesResponse } from "../domain/contract";
import { ERROR_SOURCES, type ErrorSource } from "../domain/dimensions";
import { formatBucket, formatCompact, formatDateTime, formatNumber } from "../domain/format";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "./chart-primitives";
import { SourceIcon } from "./issue-meta";

/*
 * Series colors follow the source, never its rank, so a source filter doesn't repaint the others.
 * Validated with the dataviz palette checker: light blue-600 / emerald-600 / pink-400,
 * dark blue-500 / emerald-600 / pink-500 (CVD ΔE ≥ 7.6, with a legend and the table as relief).
 */
const chartConfig = {
  platform: {
    label: "Платформа",
    theme: { light: "var(--color-blue-600)", dark: "var(--color-blue-500)" },
  },
  macos: {
    label: "macOS",
    theme: { light: "var(--color-emerald-600)", dark: "var(--color-emerald-600)" },
  },
  windows: {
    label: "Windows",
    theme: { light: "var(--color-pink-400)", dark: "var(--color-pink-500)" },
  },
} satisfies ChartConfig;

const SWATCH: Record<ErrorSource, string> = {
  platform: "bg-blue-600 dark:bg-blue-500",
  macos: "bg-emerald-600",
  windows: "bg-pink-400 dark:bg-pink-500",
};

type Props = {
  timeline: IssuesResponse["timeline"];
  /** The source filter; when set only that series is drawn. */
  source: ErrorSource | null;
  periodLabel: string;
};

export function ErrorsTimeline({ timeline, source, periodLabel }: Props) {
  const sources = ERROR_SOURCES.filter((option) => source === null || option.id === source);
  const totals = Object.fromEntries(
    sources.map((option) => [option.id, timeline.points.reduce((sum, point) => sum + point[option.id], 0)]),
  ) as Partial<Record<ErrorSource, number>>;
  const total = Object.values(totals).reduce((sum, value) => sum + (value ?? 0), 0);
  const top = sources.at(-1)?.id;

  return (
    <Card>
      <CardHeader>
        <CardTitle>События по источникам</CardTitle>
        <CardDescription>
          {formatNumber(total)} событий за {periodLabel}, по {timeline.bucket === "hour" ? "часам" : "дням"}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul aria-label="Легенда" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {sources.map((option) => (
            <li key={option.id} className="flex items-center gap-2">
              <span aria-hidden="true" className={`size-2.5 rounded-xs ${SWATCH[option.id]}`} />
              <SourceIcon source={option.id} className="size-3.5 text-muted-foreground" />
              <span>{option.label}</span>
              <span className="text-muted-foreground tabular-nums">{formatNumber(totals[option.id] ?? 0)}</span>
            </li>
          ))}
        </ul>
        {total === 0 ? (
          <p className="grid h-56 place-items-center rounded-lg border border-dashed text-muted-foreground text-sm">
            За выбранный период событий нет
          </p>
        ) : (
          <ChartContainer
            config={chartConfig}
            className="h-56 w-full"
            role="img"
            aria-label={`Столбчатая диаграмма событий за ${periodLabel}: ${sources
              .map((option) => `${option.label} — ${formatNumber(totals[option.id] ?? 0)}`)
              .join(", ")}`}
          >
            <BarChart data={timeline.points} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="bucket_start"
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                minTickGap={24}
                tickFormatter={(value: string) => formatBucket(value, timeline.bucket)}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                width={36}
                allowDecimals={false}
                tickFormatter={(value: number) => formatCompact(value)}
              />
              <ChartTooltip
                cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, payload) => {
                      const start = payload?.[0]?.payload?.bucket_start;
                      return typeof start === "string" ? formatDateTime(start) : null;
                    }}
                  />
                }
              />
              {sources.map((option) => (
                <Bar
                  key={option.id}
                  dataKey={option.id}
                  stackId="events"
                  fill={`var(--color-${option.id})`}
                  stroke="var(--card)"
                  strokeWidth={1}
                  radius={option.id === top ? [4, 4, 0, 0] : 0}
                  maxBarSize={28}
                />
              ))}
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
