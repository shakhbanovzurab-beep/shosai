"use client";

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

import { leadsChartData, proposalsChartData, revenueChartData } from "../../data/crm-v1/charts";
import { Area, AreaChart, Bar, BarChart, Line, LineChart, XAxis } from "../chart-primitives";
import { createTooltipFormatter } from "../chart-tooltip-formatter";
import { leadsChartConfig, proposalsChartConfig, revenueChartConfig } from "./chart-configs";

const monthFormatter = new Intl.DateTimeFormat("ru-RU", { month: "long" });
const numberFormatter = new Intl.NumberFormat("ru-RU");
const revenueTooltipFormatter = createTooltipFormatter(revenueChartConfig, (value) => numberFormatter.format(value));

function getLastMonthName() {
  const date = new Date();
  date.setDate(1);
  date.setMonth(date.getMonth() - 1);

  return monthFormatter.format(date);
}

const lastMonth = getLastMonthName();

function formatLastMonthLabel(label: unknown) {
  return `${lastMonth}: ${String(label)}`;
}

export function NewLeadsChart() {
  return (
    <ChartContainer className="size-full min-h-24" config={leadsChartConfig}>
      <BarChart accessibilityLayer data={leadsChartData} barSize={8}>
        <XAxis dataKey="date" tickLine={false} tickMargin={10} axisLine={false} hide />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={formatLastMonthLabel} />} />
        <Bar
          background={{ fill: "var(--color-background)", radius: 4, opacity: 0.07 }}
          dataKey="newLeads"
          stackId="a"
          fill="var(--color-newLeads)"
          radius={[0, 0, 0, 0]}
        />
        <Bar dataKey="disqualified" stackId="a" fill="var(--color-disqualified)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  );
}

export function ProposalsChart() {
  return (
    <ChartContainer className="size-full min-h-24" config={proposalsChartConfig}>
      <AreaChart
        data={proposalsChartData}
        margin={{
          left: 0,
          right: 0,
          top: 5,
        }}
      >
        <XAxis dataKey="date" tickLine={false} tickMargin={10} axisLine={false} hide />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={formatLastMonthLabel} hideIndicator />} />
        <Area
          dataKey="proposalsSent"
          fill="var(--color-proposalsSent)"
          fillOpacity={0.05}
          stroke="var(--color-proposalsSent)"
          strokeWidth={2}
          type="monotone"
        />
      </AreaChart>
    </ChartContainer>
  );
}

export function RevenueGrowthChart() {
  return (
    <ChartContainer config={revenueChartConfig} className="h-24 w-full">
      <LineChart
        data={revenueChartData}
        margin={{
          top: 5,
          right: 10,
          left: 10,
          bottom: 0,
        }}
      >
        <XAxis dataKey="month" tickLine={false} tickMargin={10} axisLine={false} hide />
        <ChartTooltip content={<ChartTooltipContent formatter={revenueTooltipFormatter} />} />
        <Line
          type="monotone"
          strokeWidth={2}
          dataKey="revenue"
          stroke="var(--color-revenue)"
          activeDot={{
            r: 6,
          }}
        />
      </LineChart>
    </ChartContainer>
  );
}
