"use client";

import { Ellipsis } from "lucide-react";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { lazyComponent } from "@/lib/lazy-component";

const RealtimeVisitorsChart = lazyComponent(
  () => import("./realtime-visitors-chart").then((chartModule) => chartModule.RealtimeVisitorsChart),
  { loading: () => <Skeleton className="h-36 w-full" /> },
);

export function RealtimeVisitors() {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="font-normal">Посетители в реальном времени</CardTitle>
        <CardAction>
          <Ellipsis className="size-4" />
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex items-end justify-between">
          <div className="flex items-baseline gap-1">
            <span className="text-2xl tabular-nums leading-none tracking-tight">24</span>
            <span className="text-muted-foreground text-sm">в минуту</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-green-500 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-green-500" />
            </span>
            <span>Онлайн</span>
          </div>
        </div>
        <RealtimeVisitorsChart />
        <div className="grid grid-cols-2">
          <div className="flex items-center gap-3 border-border/50 border-r border-b pt-1 pr-5 pb-4">
            <span aria-hidden="true" className="flag:US shrink-0 rounded-xs text-lg ring-1 ring-foreground/10" />
            <span className="min-w-0 flex-1 truncate text-sm">США</span>
            <span className="text-sm tabular-nums">14</span>
          </div>
          <div className="flex items-center gap-3 border-border/50 border-b pt-1 pb-4 pl-5">
            <span aria-hidden="true" className="flag:GB shrink-0 rounded-xs text-lg ring-1 ring-foreground/10" />
            <span className="min-w-0 flex-1 truncate text-sm">Великобритания</span>
            <span className="text-sm tabular-nums">4</span>
          </div>
          <div className="flex items-center gap-3 border-border/50 border-r pt-4 pr-5 pb-1">
            <span aria-hidden="true" className="flag:CA shrink-0 rounded-xs text-lg ring-1 ring-foreground/10" />
            <span className="min-w-0 flex-1 truncate text-sm">Канада</span>
            <span className="text-sm tabular-nums">3</span>
          </div>
          <div className="flex items-center gap-3 pt-4 pb-1 pl-5">
            <span aria-hidden="true" className="flag:IN shrink-0 rounded-xs text-lg ring-1 ring-foreground/10" />
            <span className="min-w-0 flex-1 truncate text-sm">Индия</span>
            <span className="text-sm tabular-nums">3</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
