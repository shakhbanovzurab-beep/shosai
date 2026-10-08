"use client";

import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { ChartTooltipContent } from "@/components/ui/chart-tooltip";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "../chart-primitives";

const pipelineChartConfig = {
  qualified: {
    label: "Квалифицированные",
    color: "var(--chart-2)",
  },
} satisfies ChartConfig;

const axisMonthFormatter = new Intl.DateTimeFormat("ru-RU", { month: "short" });
const tooltipMonthFormatter = new Intl.DateTimeFormat("ru-RU", { month: "short", year: "2-digit" });

export type QualifiedLeadFlowDatum = {
  date: string;
  qualified: number;
};

export function QualifiedLeadFlowChart({ data }: { data: QualifiedLeadFlowDatum[] }) {
  return (
    <ChartContainer config={pipelineChartConfig} className="h-72 w-full">
      <BarChart data={data} margin={{ left: 0, right: 0, top: 0, bottom: 0 }} barSize={38}>
        <defs>
          <pattern
            id="crm-qualified-pattern"
            width="4"
            height="4"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="var(--color-qualified)" fillOpacity="0.15" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-qualified)" strokeWidth="1.25" strokeOpacity="0.40" />
          </pattern>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="0" />
        <XAxis
          dataKey="date"
          tickLine={false}
          tickMargin={10}
          axisLine={false}
          tickFormatter={(value) => axisMonthFormatter.format(new Date(String(value)))}
        />
        <YAxis hide />
        <ChartTooltip
          content={
            <ChartTooltipContent
              hideIndicator
              labelFormatter={(value) => tooltipMonthFormatter.format(new Date(String(value)))}
            />
          }
        />
        <Bar
          dataKey="qualified"
          fill="url(#crm-qualified-pattern)"
          radius={[8, 8, 0, 0]}
          stroke="var(--color-qualified)"
          strokeOpacity={0.5}
          strokeWidth={0.5}
        />
      </BarChart>
    </ChartContainer>
  );
}
