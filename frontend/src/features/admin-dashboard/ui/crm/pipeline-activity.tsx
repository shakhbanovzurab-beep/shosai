"use client";

import dynamic from "next/dynamic";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { pluralizeRu } from "@/lib/plural";

const QualifiedLeadFlowChart = dynamic(
  () => import("./qualified-lead-flow-chart").then((chartModule) => chartModule.QualifiedLeadFlowChart),
  { loading: () => <Skeleton className="h-72 w-full" /> },
);

const pipelineChartValues = [34, 38, 31, 47, 42, 51, 44, 40, 58, 46, 43, 49] as const;

const leadForms = ["лид", "лида", "лидов"] as const;
const meetingForms = ["встреча", "встречи", "встреч"] as const;

function getRollingMonthData(values: readonly number[]) {
  return values.map((qualified, index) => {
    const date = new Date();
    date.setMonth(date.getMonth() - (values.length - 1 - index));

    return {
      date: date.toISOString(),
      qualified,
    };
  });
}

export function PipelineActivity() {
  const pipelineChartData = getRollingMonthData(pipelineChartValues);
  const totalQualified = pipelineChartData.reduce((sum, item) => sum + item.qualified, 0);
  const discoveryCallsBooked = 184;
  const discoveryProgress = Math.round((discoveryCallsBooked / totalQualified) * 100);

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <Card className="xl:col-span-12">
        <CardHeader>
          <CardTitle>Поток квалифицированных лидов</CardTitle>
          <CardAction>
            <Select defaultValue="last-12-months">
              <SelectTrigger size="sm" className="min-w-44">
                <SelectValue placeholder="Выберите период" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="last-30-days">За 30 дней</SelectItem>
                  <SelectItem value="last-quarter">За прошлый квартал</SelectItem>
                  <SelectItem value="last-12-months">За 12 месяцев</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="lg:col-span-8">
              <QualifiedLeadFlowChart data={pipelineChartData} />
            </div>

            <div className="flex flex-col gap-5 rounded-lg p-4 lg:col-span-4">
              <div className="flex flex-col gap-1">
                <div className="font-medium text-4xl tabular-nums leading-none">
                  {totalQualified}{" "}
                  <span className="font-normal text-lg text-muted-foreground">
                    {pluralizeRu(totalQualified, leadForms)}
                  </span>
                </div>
                <p className="text-muted-foreground text-sm">Всего квалифицированных лидов за последние 12 месяцев.</p>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border border-border/60 p-3">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">
                  Назначено первичных звонков
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="font-medium text-2xl tabular-nums leading-none">
                    {discoveryCallsBooked}{" "}
                    <span className="font-normal text-muted-foreground text-sm">
                      {pluralizeRu(discoveryCallsBooked, meetingForms)}
                    </span>
                  </div>
                  <p className="text-muted-foreground text-sm">
                    {discoveryProgress}% квалифицированных лидов назначили первый звонок.
                  </p>
                </div>

                <div className="flex flex-col gap-2 pt-0.5">
                  <Progress
                    value={discoveryProgress}
                    className="h-2.5 bg-chart-2/12 *:data-[slot='progress-indicator']:bg-chart-2"
                  />
                  <div className="flex items-center justify-between text-xs">
                    <div className="font-medium tabular-nums">{discoveryCallsBooked} назначено</div>
                    <div className="text-muted-foreground tabular-nums">{totalQualified} квалифицировано</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
