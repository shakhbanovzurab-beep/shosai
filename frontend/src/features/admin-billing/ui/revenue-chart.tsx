"use client";

// Ложное срабатывание: модуль грузится только лениво (lazyComponent), recharts — в отдельном чанке.
// react-doctor-disable-next-line react-doctor/prefer-dynamic-import
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartConfig, ChartContainer, ChartLegend, ChartTooltip } from "@/components/ui/chart";
import { ChartLegendContent } from "@/components/ui/chart-legend";
import { ChartTooltipContent } from "@/components/ui/chart-tooltip";

import { type Currency, type MonthRevenue, PAID_PLANS, type PaidPlanId } from "../domain/contract";
import { formatMoney, formatMoneyCompact, formatMonthLong, formatMonthShort } from "../domain/format";
import { PLAN_LABELS } from "../domain/labels";

const chartConfig = {
  professional: { label: PLAN_LABELS.professional, color: "var(--chart-1)" },
  team: { label: PLAN_LABELS.team, color: "var(--chart-2)" },
  enterprise: { label: PLAN_LABELS.enterprise, color: "var(--chart-3)" },
} satisfies ChartConfig;

/** The top segment of each stack gets the rounded data-end. */
const RADIUS: Record<PaidPlanId, [number, number, number, number]> = {
  professional: [0, 0, 0, 0],
  team: [0, 0, 0, 0],
  enterprise: [4, 4, 0, 0],
};

const monthTotal = (row: MonthRevenue) => row.professional + row.team + row.enterprise;

export function RevenueChart({ currency, months }: { currency: Currency; months: MonthRevenue[] }) {
  const total = months.reduce((sum, row) => sum + monthTotal(row), 0);
  const current = months.at(-1)?.month;

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Выручка по тарифам</CardTitle>
        <CardDescription>
          За 12 месяцев <span className="font-medium text-foreground tabular-nums">{formatMoney(total, currency)}</span>{" "}
          за вычетом возвратов; текущий месяц ещё не закончился
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        <ChartContainer config={chartConfig} className="aspect-auto h-72 min-h-64 w-full flex-1" aria-hidden="true">
          <BarChart data={months} margin={{ left: 0, right: 0, top: 8, bottom: 0 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={(value) => formatMonthShort(String(value))}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={72}
              tickFormatter={(value) => formatMoneyCompact(Number(value), currency)}
            />
            <ChartTooltip
              cursor={{ fill: "var(--muted)", opacity: 0.5 }}
              content={
                <ChartTooltipContent
                  className="min-w-48"
                  labelFormatter={(_, payload) => {
                    const row = payload[0]?.payload as MonthRevenue | undefined;
                    if (!row) return null;
                    return `${formatMonthLong(row.month)}${row.month === current ? " — неполный" : ""}: ${formatMoney(monthTotal(row), currency)}`;
                  }}
                  formatter={(value, name, item) => (
                    <>
                      <span className="size-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: item.color }} />
                      <span className="flex flex-1 items-center justify-between gap-4 leading-none">
                        <span className="text-muted-foreground">{PLAN_LABELS[name as PaidPlanId] ?? name}</span>
                        <span className="font-medium text-foreground tabular-nums">
                          {formatMoney(Number(value), currency)}
                        </span>
                      </span>
                    </>
                  )}
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            {PAID_PLANS.map((plan) => (
              <Bar
                key={plan}
                dataKey={plan}
                stackId="revenue"
                fill={`var(--color-${plan})`}
                stroke="var(--card)"
                strokeWidth={1}
                radius={RADIUS[plan]}
                maxBarSize={40}
              />
            ))}
          </BarChart>
        </ChartContainer>

        <table className="sr-only">
          <caption>Выручка по тарифам за последние 12 месяцев</caption>
          <thead>
            <tr>
              <th scope="col">Месяц</th>
              {PAID_PLANS.map((plan) => (
                <th key={plan} scope="col">
                  {PLAN_LABELS[plan]}
                </th>
              ))}
              <th scope="col">Итого</th>
            </tr>
          </thead>
          <tbody>
            {months.map((row) => (
              <tr key={row.month}>
                <th scope="row">{formatMonthLong(row.month)}</th>
                {PAID_PLANS.map((plan) => (
                  <td key={plan}>{formatMoney(row[plan], currency)}</td>
                ))}
                <td>{formatMoney(monthTotal(row), currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
