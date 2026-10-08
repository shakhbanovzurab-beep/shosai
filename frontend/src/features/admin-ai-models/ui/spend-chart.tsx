"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { lazyComponent } from "@/lib/lazy-component";

import type { DailySpend } from "../domain/contract";
import { formatLongDate, formatUsd } from "../domain/format";

const SpendAreaChart = lazyComponent(
  () => import("./spend-area-chart").then((chartModule) => chartModule.SpendAreaChart),
  {
    loading: () => <Skeleton className="h-64 w-full" />,
  },
);

export function SpendChart({ daily }: { daily: DailySpend[] }) {
  const total = daily.reduce((sum, day) => sum + day.cost, 0);

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="font-normal">Расход за 30 дней</CardTitle>
        <CardDescription>
          Всего <span className="text-foreground tabular-nums">{formatUsd(total)}</span>, по дням (UTC)
        </CardDescription>
      </CardHeader>
      <CardContent>
        {total > 0 ? (
          <>
            <SpendAreaChart daily={daily} />
            <table className="sr-only">
              <caption>Расход по дням</caption>
              <thead>
                <tr>
                  <th scope="col">Дата</th>
                  <th scope="col">Расход</th>
                </tr>
              </thead>
              <tbody>
                {daily.map((day) => (
                  <tr key={day.date}>
                    <td>{formatLongDate(day.date)}</td>
                    <td>{formatUsd(day.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="flex h-64 items-center justify-center text-muted-foreground text-sm">
            За последние 30 дней расходов не было.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
