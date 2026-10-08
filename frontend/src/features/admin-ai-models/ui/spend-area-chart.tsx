"use client";

// Ложное срабатывание: модуль грузится только лениво (lazyComponent), recharts — в отдельном чанке.
// react-doctor-disable-next-line react-doctor/prefer-dynamic-import
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { ChartTooltipContent } from "@/components/ui/chart-tooltip";

import type { DailySpend } from "../domain/contract";
import { formatLongDate, formatShortDate, formatUsd } from "../domain/format";

const chartConfig = {
  cost: { label: "Расход", color: "var(--chart-2)" },
} satisfies ChartConfig;

const usdTick = (value: number) => `$${value}`;

export function SpendAreaChart({ daily }: { daily: DailySpend[] }) {
  return (
    <ChartContainer config={chartConfig} className="aspect-auto h-64 w-full" aria-hidden="true">
      <AreaChart data={daily} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="ai-spend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-cost)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--color-cost)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={32}
          tickFormatter={formatShortDate}
        />
        <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={usdTick} />
        <ChartTooltip
          cursor={{ stroke: "var(--border)" }}
          content={
            <ChartTooltipContent
              labelFormatter={(_, payload) => {
                const date = payload[0]?.payload?.date;
                return typeof date === "string" ? formatLongDate(date) : null;
              }}
              formatter={(value) => (
                <div className="flex w-full items-center justify-between gap-4">
                  <span className="text-muted-foreground">Расход</span>
                  <span className="font-medium font-mono text-foreground tabular-nums">{formatUsd(Number(value))}</span>
                </div>
              )}
            />
          }
        />
        <Area
          dataKey="cost"
          type="monotone"
          stroke="var(--color-cost)"
          strokeWidth={2}
          fill="url(#ai-spend-fill)"
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ChartContainer>
  );
}
