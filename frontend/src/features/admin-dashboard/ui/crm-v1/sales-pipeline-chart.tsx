"use client";

// Ложное срабатывание: модуль грузится только лениво (lazyComponent), recharts — в отдельном чанке.
// react-doctor-disable-next-line react-doctor/prefer-dynamic-import
import { Funnel, FunnelChart, LabelList } from "recharts";

import { ChartContainer } from "@/components/ui/chart";

import { salesPipelineChartData } from "../../data/crm-v1/charts";
import { salesPipelineChartConfig } from "./chart-configs";

export function SalesPipelineChart() {
  return (
    <ChartContainer config={salesPipelineChartConfig} className="size-full">
      <FunnelChart margin={{ left: 0, right: 0, top: 0, bottom: 0 }}>
        <Funnel className="stroke-2 stroke-card" dataKey="value" data={salesPipelineChartData}>
          <LabelList className="fill-foreground stroke-0" dataKey="stage" position="right" offset={10} />
          <LabelList className="fill-foreground stroke-0" dataKey="value" position="left" offset={10} />
        </Funnel>
      </FunnelChart>
    </ChartContainer>
  );
}
