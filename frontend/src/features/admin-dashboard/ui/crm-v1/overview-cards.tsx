"use client";

import dynamic from "next/dynamic";

import { BadgeDollarSign, Wallet } from "lucide-react";

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const NewLeadsChart = dynamic(() => import("./overview-charts").then((chartModule) => chartModule.NewLeadsChart), {
  loading: () => <Skeleton className="size-full min-h-24" />,
});

const ProposalsChart = dynamic(() => import("./overview-charts").then((chartModule) => chartModule.ProposalsChart), {
  loading: () => <Skeleton className="size-full min-h-24 rounded-none" />,
});

const RevenueGrowthChart = dynamic(
  () => import("./overview-charts").then((chartModule) => chartModule.RevenueGrowthChart),
  { loading: () => <Skeleton className="h-24 w-full" /> },
);

const usdFormatter = new Intl.NumberFormat("ru-RU", {
  currency: "USD",
  maximumFractionDigits: 0,
  style: "currency",
});

export function OverviewCards() {
  return (
    <div className="grid grid-cols-1 gap-4 *:data-[slot=card]:shadow-xs sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <Card>
        <CardHeader>
          <CardTitle>Новые лиды</CardTitle>
          <CardDescription>За прошлый месяц</CardDescription>
        </CardHeader>
        <CardContent className="size-full">
          <NewLeadsChart />
        </CardContent>
        <CardFooter className="flex items-center justify-between">
          <span className="font-semibold text-xl tabular-nums">635</span>
          <span className="font-medium text-green-500 text-sm">+54,6%</span>
        </CardFooter>
      </Card>

      <Card className="overflow-hidden pb-0">
        <CardHeader>
          <CardTitle>Отправлено КП</CardTitle>
          <CardDescription>За прошлый месяц</CardDescription>
        </CardHeader>
        <CardContent className="flex-1 p-0">
          <ProposalsChart />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="w-fit rounded-lg bg-green-500/10 p-2">
            <Wallet className="size-5 text-green-500" />
          </div>
        </CardHeader>
        <CardContent className="flex size-full flex-col justify-between">
          <div className="space-y-1.5">
            <CardTitle>Выручка</CardTitle>
            <CardDescription>За 6 месяцев</CardDescription>
          </div>
          <p className="font-medium text-2xl tabular-nums">{usdFormatter.format(56_050)}</p>
          <div className="w-fit rounded-md bg-green-500/10 px-2 py-1 font-medium text-green-500 text-xs">+22,2%</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="w-fit rounded-lg bg-destructive/10 p-2">
            <BadgeDollarSign className="size-5 text-destructive" />
          </div>
        </CardHeader>
        <CardContent className="flex size-full flex-col justify-between">
          <div className="space-y-1.5">
            <CardTitle>Выиграно проектов</CardTitle>
            <CardDescription>За 6 месяцев</CardDescription>
          </div>
          <p className="font-medium text-2xl tabular-nums">136</p>
          <div className="w-fit rounded-md bg-destructive/10 px-2 py-1 font-medium text-destructive text-xs">-2,5%</div>
        </CardContent>
      </Card>

      <Card className="col-span-1 xl:col-span-2">
        <CardHeader>
          <CardTitle>Рост выручки</CardTitle>
          <CardDescription>С начала года</CardDescription>
        </CardHeader>
        <CardContent>
          <RevenueGrowthChart />
        </CardContent>
        <CardFooter>
          <p className="text-muted-foreground text-sm">Рост на 35% по сравнению с прошлым годом</p>
        </CardFooter>
      </Card>
    </div>
  );
}
