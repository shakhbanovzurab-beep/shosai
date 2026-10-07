"use client";

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

import { leadsBySourceChartData, projectRevenueChartData } from "../../data/crm-v1/charts";
import { Bar, BarChart, CartesianGrid, Label, LabelList, Pie, PieChart, XAxis, YAxis } from "../chart-primitives";
import { createTooltipFormatter } from "../chart-tooltip-formatter";
import { leadsBySourceChartConfig, projectRevenueChartConfig } from "./chart-configs";

const numberFormatter = new Intl.NumberFormat("ru-RU");
const totalLeads = leadsBySourceChartData.reduce((acc, curr) => acc + curr.leads, 0);
const projectRevenueTooltipFormatter = createTooltipFormatter(
  projectRevenueChartConfig,
  (value) => numberFormatter.format(value),
  "line",
);

function formatLabelNumber(value: unknown) {
  return typeof value === "number" ? numberFormatter.format(value) : String(value ?? "");
}

export function LeadsBySourceChart() {
  return (
    <ChartContainer config={leadsBySourceChartConfig} className="mx-auto aspect-square max-h-48 flex-1">
      <PieChart
        className="m-0"
        margin={{
          top: 0,
          right: 0,
          left: 0,
          bottom: 0,
        }}
      >
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
        <Pie
          data={leadsBySourceChartData}
          dataKey="leads"
          nameKey="source"
          innerRadius={65}
          outerRadius={90}
          paddingAngle={2}
          cornerRadius={4}
        >
          <Label
            content={({ viewBox }) => {
              if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                return (
                  <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                    <tspan x={viewBox.cx} y={viewBox.cy} className="fill-foreground font-bold text-3xl tabular-nums">
                      {numberFormatter.format(totalLeads)}
                    </tspan>
                    <tspan x={viewBox.cx} y={(viewBox.cy || 0) + 24} className="fill-muted-foreground">
                      Лиды
                    </tspan>
                  </text>
                );
              }
            }}
          />
        </Pie>
      </PieChart>
    </ChartContainer>
  );
}

export function ProjectRevenueChart() {
  return (
    <ChartContainer config={projectRevenueChartConfig} className="size-full">
      <BarChart accessibilityLayer data={projectRevenueChartData} layout="vertical">
        <CartesianGrid horizontal={false} />
        <YAxis
          dataKey="name"
          type="category"
          tickLine={false}
          tickMargin={10}
          axisLine={false}
          tickFormatter={(value) => value.slice(0, 3)}
          hide
        />
        <XAxis dataKey="actual" type="number" hide />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent indicator="line" formatter={projectRevenueTooltipFormatter} />}
        />
        <Bar stackId="a" dataKey="actual" fill="var(--color-actual)">
          <LabelList dataKey="name" position="insideLeft" offset={8} className="fill-primary-foreground text-xs" />
          <LabelList
            dataKey="actual"
            position="insideRight"
            offset={8}
            className="fill-primary-foreground text-xs tabular-nums"
            formatter={formatLabelNumber}
          />
        </Bar>
        <Bar stackId="a" dataKey="remaining" fill="var(--color-remaining)" radius={[0, 6, 6, 0]}>
          <LabelList
            dataKey="remaining"
            position="insideRight"
            offset={8}
            className="fill-primary-foreground text-xs tabular-nums"
            formatter={formatLabelNumber}
          />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
