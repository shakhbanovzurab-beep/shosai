"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

import type { LiveKitHistoryPoint } from "../domain/contract";
import { formatInteger, formatMbps, formatTime } from "../domain/format";
import { Area, AreaChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "./chart-primitives";

const participantsConfig = {
  participants: { label: "Участники", color: "var(--chart-1)" },
} satisfies ChartConfig;

const bandwidthConfig = {
  bandwidth_in_mbps: { label: "Входящий", color: "var(--chart-1)" },
  bandwidth_out_mbps: { label: "Исходящий", color: "var(--chart-2)" },
} satisfies ChartConfig;

const CHART_MARGIN = { left: 0, right: 8, top: 8, bottom: 0 };
const formatTick = (value: unknown) => formatTime(String(value));
const formatLabel = (value: unknown) => `Время: ${formatTime(String(value))}`;
const labelOf = (config: ChartConfig, name: unknown) => config[String(name)]?.label ?? String(name);

/** A tooltip row with the series swatch, its Russian label and a ru-RU value. */
function tooltipRow(config: ChartConfig, format: (value: number) => string) {
  return (value: unknown, name: unknown, item: { color?: string }) => (
    <div className="flex w-full items-center gap-2">
      <span aria-hidden="true" className="size-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: item.color }} />
      <span className="text-muted-foreground">{labelOf(config, name)}</span>
      <span className="ml-auto pl-3 font-medium font-mono text-foreground tabular-nums">{format(Number(value))}</span>
    </div>
  );
}

const participantsRow = tooltipRow(participantsConfig, formatInteger);
const bandwidthRow = tooltipRow(bandwidthConfig, formatMbps);

function peak(history: LiveKitHistoryPoint[], key: "participants" | "bandwidth_out_mbps") {
  let best = history[0];
  for (const point of history) if (best === undefined || point[key] > best[key]) best = point;
  return best;
}

export function HistoryCharts({ history }: { history: LiveKitHistoryPoint[] }) {
  const peakParticipants = peak(history, "participants");
  const peakBandwidth = peak(history, "bandwidth_out_mbps");

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Участники за 24 часа</CardTitle>
          <CardDescription>
            {peakParticipants
              ? `Пик — ${formatInteger(peakParticipants.participants)} в ${formatTime(peakParticipants.at)}`
              : "Нет данных"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer
            config={participantsConfig}
            className="aspect-auto h-64 w-full"
            role="img"
            aria-label="График числа участников онлайн за последние 24 часа"
          >
            <AreaChart data={history} margin={CHART_MARGIN}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="at"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={40}
                tickFormatter={formatTick}
              />
              <YAxis tickLine={false} axisLine={false} width={32} allowDecimals={false} tickFormatter={formatInteger} />
              <ChartTooltip
                content={<ChartTooltipContent labelFormatter={formatLabel} formatter={participantsRow} />}
              />
              <Area
                dataKey="participants"
                type="monotone"
                fill="var(--color-participants)"
                fillOpacity={0.15}
                stroke="var(--color-participants)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </AreaChart>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Трафик за 24 часа, Мбит/с</CardTitle>
          <CardDescription>
            {peakBandwidth
              ? `Пик исходящего — ${formatMbps(peakBandwidth.bandwidth_out_mbps)} в ${formatTime(peakBandwidth.at)}`
              : "Нет данных"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer
            config={bandwidthConfig}
            className="aspect-auto h-64 w-full"
            role="img"
            aria-label="График входящего и исходящего трафика за последние 24 часа"
          >
            <LineChart data={history} margin={CHART_MARGIN}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="at"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={40}
                tickFormatter={formatTick}
              />
              <YAxis tickLine={false} axisLine={false} width={40} tickFormatter={formatInteger} />
              <ChartTooltip content={<ChartTooltipContent labelFormatter={formatLabel} formatter={bandwidthRow} />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Line
                dataKey="bandwidth_in_mbps"
                type="monotone"
                stroke="var(--color-bandwidth_in_mbps)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                dataKey="bandwidth_out_mbps"
                type="monotone"
                stroke="var(--color-bandwidth_out_mbps)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  );
}
