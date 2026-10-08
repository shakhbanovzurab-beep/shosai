"use client";

import { cn } from "cn";
import { Clock } from "lucide-react";

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { lazyComponent } from "@/lib/lazy-component";
import { pluralizeRu } from "@/lib/plural";

import { actionItems, regionSalesData } from "../../data/crm-v1/operations";

const SalesPipelineChart = lazyComponent(
  () => import("./sales-pipeline-chart").then((chartModule) => chartModule.SalesPipelineChart),
  { loading: () => <Skeleton className="size-full min-h-48" /> },
);

const usdFormatter = new Intl.NumberFormat("ru-RU", {
  currency: "USD",
  maximumFractionDigits: 0,
  style: "currency",
});

const priorityLabels: Record<string, string> = {
  High: "Высокий",
  Medium: "Средний",
  Low: "Низкий",
};

function formatRegionCount(count: number) {
  return `${count} ${pluralizeRu(count, ["регион", "региона", "регионов"])}`;
}

export function OperationalCards() {
  const totalSales = regionSalesData.reduce((sum, region) => sum + region.sales, 0);
  return (
    <div className="grid grid-cols-1 gap-4 *:data-[slot=card]:shadow-xs sm:grid-cols-2 xl:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>Воронка продаж</CardTitle>
        </CardHeader>
        <CardContent className="size-full">
          <SalesPipelineChart />
        </CardContent>
        <CardFooter>
          <p className="text-muted-foreground text-xs">Число лидов выросло на 18,2% за месяц.</p>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Продажи по регионам</CardTitle>
          <CardDescription className="font-medium tabular-nums">{usdFormatter.format(totalSales)}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2.5">
            {regionSalesData.map((region) => (
              <div key={region.region} className="space-y-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate font-medium text-sm">{region.region}</span>
                  <div className="flex shrink-0 items-baseline gap-1">
                    <span className="font-semibold text-sm tabular-nums">{usdFormatter.format(region.sales)}</span>
                    <span
                      className={cn(
                        "font-medium text-xs tabular-nums",
                        region.isPositive ? "text-green-500" : "text-destructive",
                      )}
                    >
                      {region.growth}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Progress value={region.percentage} />
                  <span className="font-medium text-muted-foreground text-xs tabular-nums">{region.percentage}%</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
        <CardFooter>
          <div className="flex justify-between gap-1 text-muted-foreground text-xs">
            <span>Отслеживается: {formatRegionCount(regionSalesData.length)}</span>
            <span>•</span>
            <span>Растут: {formatRegionCount(regionSalesData.filter((r) => r.isPositive).length)}</span>
          </div>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Задачи</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2.5">
            {actionItems.map((item) => (
              <li key={item.id} className="space-y-2 rounded-md border px-3 py-2">
                <div className="flex items-center gap-2">
                  <Checkbox defaultChecked={item.checked} aria-label={`Отметить задачу «${item.title}» выполненной`} />
                  <span className="font-medium text-sm">{item.title}</span>
                  <span
                    className={cn(
                      "w-fit rounded-md px-2 py-1 font-medium text-xs",
                      item.priority === "High" && "bg-destructive/20 text-destructive",
                      item.priority === "Medium" && "bg-yellow-500/20 text-yellow-500",
                      item.priority === "Low" && "bg-green-500/20 text-green-500",
                    )}
                  >
                    {priorityLabels[item.priority] ?? item.priority}
                  </span>
                </div>
                <div className="font-medium text-muted-foreground text-xs">{item.desc}</div>
                <div className="flex items-center gap-1">
                  <Clock className="size-3 text-muted-foreground" />
                  <span className="font-medium text-muted-foreground text-xs">{item.due}</span>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
