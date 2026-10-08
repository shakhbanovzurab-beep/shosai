"use client";

// Ложное срабатывание: модуль грузится только лениво (lazyComponent), recharts — в отдельном чанке.
// react-doctor-disable-next-line react-doctor/prefer-dynamic-import
import { CartesianGrid, ComposedChart, Line, XAxis, YAxis } from "recharts";

import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { ChartTooltipContent } from "@/components/ui/chart-tooltip";

import { qualitySeries } from "../../data/analytics/traffic-quality";
import { createTooltipFormatter } from "../chart-tooltip-formatter";

const chartConfig = {
  actualQuality: {
    color: "var(--chart-3)",
    label: "Фактическое качество",
  },
  baselineQuality: {
    color: "var(--muted-foreground)",
    label: "Базовый уровень",
  },
} satisfies ChartConfig;

const chartData = qualitySeries.map((item, index) => ({
  ...item,
  dayIndex: 1 + (index * 27) / (qualitySeries.length - 1),
}));

const qualityFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const qualityTooltipFormatter = createTooltipFormatter(chartConfig, (value) => qualityFormatter.format(value));

const weeklyTicks = [4, 11, 18, 25];

function formatWeek(value: number) {
  const weekIndex = weeklyTicks.indexOf(value);

  return weekIndex >= 0 ? `Неделя ${weekIndex + 1}` : "";
}

export function TrafficQualityChart() {
  return (
    <ChartContainer config={chartConfig} className="h-68 w-full">
      <ComposedChart data={chartData} margin={{ bottom: 0, left: 0, right: 0, top: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="dayIndex"
          axisLine={false}
          domain={[1, 28]}
          interval={0}
          tickFormatter={formatWeek}
          tickLine={false}
          tickMargin={14}
          ticks={weeklyTicks}
          type="number"
        />
        <YAxis
          axisLine={false}
          domain={[-6, 6]}
          tickFormatter={(value) => `${value}%`}
          tickLine={false}
          tickMargin={10}
          width={34}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              className="w-52"
              formatter={qualityTooltipFormatter}
              labelFormatter={() => "Качество трафика"}
            />
          }
        />
        <Line
          dataKey="baselineQuality"
          dot={false}
          stroke="var(--color-baselineQuality)"
          strokeOpacity={0.65}
          strokeDasharray="4 4"
          strokeWidth={1.75}
          type="linear"
        />
        <Line
          dataKey="actualQuality"
          dot={false}
          activeDot={{ r: 4 }}
          stroke="var(--color-actualQuality)"
          strokeWidth={2.5}
          type="linear"
        />
      </ComposedChart>
    </ChartContainer>
  );
}
