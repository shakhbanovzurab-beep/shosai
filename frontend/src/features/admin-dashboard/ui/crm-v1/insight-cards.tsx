"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { lazyComponent } from "@/lib/lazy-component";

import { leadsBySourceChartData } from "../../data/crm-v1/charts";
import { leadsBySourceChartConfig } from "./chart-configs";

const LeadsBySourceChart = lazyComponent(
  () => import("./insight-charts").then((chartModule) => chartModule.LeadsBySourceChart),
  { loading: () => <Skeleton className="mx-auto aspect-square max-h-48 flex-1 rounded-full" /> },
);

const ProjectRevenueChart = lazyComponent(
  () => import("./insight-charts").then((chartModule) => chartModule.ProjectRevenueChart),
  { loading: () => <Skeleton className="size-full min-h-40" /> },
);

export function InsightCards() {
  return (
    <div className="grid grid-cols-1 gap-4 *:data-[slot=card]:shadow-xs sm:grid-cols-2 xl:grid-cols-5">
      <Card className="col-span-1 xl:col-span-2">
        <CardHeader>
          <CardTitle>Лиды по источникам</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-6">
          <LeadsBySourceChart />

          <ul className="flex flex-col gap-3">
            {leadsBySourceChartData.map((item) => (
              <li key={item.source} className="flex w-40 items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2 text-xs">
                  <span
                    className="size-2.5 shrink-0 rounded-full"
                    style={{
                      background:
                        "color" in leadsBySourceChartConfig[item.source]
                          ? leadsBySourceChartConfig[item.source].color
                          : undefined,
                    }}
                  />
                  <span className="truncate">{leadsBySourceChartConfig[item.source].label}</span>
                </span>
                <span className="text-xs tabular-nums">{item.leads}</span>
              </li>
            ))}
          </ul>
        </CardContent>
        <CardFooter className="gap-2">
          <Button size="sm" variant="outline" className="min-w-0 basis-1/2">
            <span className="truncate">Полный отчёт</span>
          </Button>
          <Button size="sm" variant="outline" className="min-w-0 basis-1/2">
            <span className="truncate">Скачать CSV</span>
          </Button>
        </CardFooter>
      </Card>

      <Card className="col-span-1 xl:col-span-3">
        <CardHeader>
          <CardTitle>Выручка по проектам и план</CardTitle>
        </CardHeader>
        <CardContent className="size-full max-h-52">
          <ProjectRevenueChart />
        </CardContent>
        <CardFooter>
          <p className="text-muted-foreground text-xs">Средний прогресс: 78% · 2 проекта выше плана</p>
        </CardFooter>
      </Card>
    </div>
  );
}
