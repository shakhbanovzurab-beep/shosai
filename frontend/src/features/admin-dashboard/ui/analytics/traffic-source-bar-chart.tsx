"use client";

import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { ChartTooltipContent } from "@/components/ui/chart-tooltip";

import { Bar, BarChart, CartesianGrid, LabelList, type LabelProps, XAxis, YAxis } from "../chart-primitives";
import { createTooltipFormatter } from "../chart-tooltip-formatter";

const chartConfig = {
  visitors: {
    color: "var(--chart-1)",
    label: "Посетители",
  },
} satisfies ChartConfig;

const visitorsFormatter = new Intl.NumberFormat("ru-RU");
const visitorsTooltipFormatter = createTooltipFormatter(
  chartConfig,
  (value) => visitorsFormatter.format(value),
  "line",
);

type TrafficSourceDatum = {
  label: string;
  source: string;
  visitors: number;
};

function renderValueLabel(props: LabelProps) {
  const { height, value, y } = props;

  return (
    <text
      className="fill-foreground"
      dominantBaseline="middle"
      dx={-6}
      fontSize={14}
      textAnchor="end"
      x="100%"
      y={Number(y) + Number(height) / 2}
    >
      {value}
    </text>
  );
}

export function TrafficSourceBarChart({ data }: { data: TrafficSourceDatum[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-64 w-full">
      <BarChart
        accessibilityLayer
        data={data}
        layout="vertical"
        margin={{
          left: 0,
          right: 72,
        }}
      >
        <CartesianGrid horizontal={false} vertical={false} />
        <YAxis dataKey="source" hide tickLine={false} tickMargin={10} type="category" />
        <XAxis dataKey="visitors" hide type="number" />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent indicator="line" formatter={visitorsTooltipFormatter} />}
        />
        <Bar barSize={40} dataKey="visitors" fill="var(--color-visitors)" fillOpacity={0.5} radius={8}>
          <LabelList className="fill-foreground" dataKey="source" fontSize={14} offset={12} position="insideLeft" />
          <LabelList content={renderValueLabel} dataKey="label" />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
