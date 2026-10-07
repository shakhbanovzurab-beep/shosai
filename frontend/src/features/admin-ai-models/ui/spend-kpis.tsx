import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { AiDataSource, AiModel, SpendSummary } from "../domain/contract";
import { formatCompact, formatInteger, formatUsd } from "../domain/format";

type Kpi = { label: string; value: string; note: string };

export function SpendKpis({ spend, models, source }: { spend: SpendSummary; models: AiModel[]; source: AiDataSource }) {
  const requests = models.reduce((sum, model) => sum + model.month_requests, 0);
  const kpis: Kpi[] = [
    { label: "Сегодня", value: formatUsd(spend.today), note: "с 00:00 UTC" },
    { label: "С начала месяца", value: formatUsd(spend.month), note: `${formatInteger(requests)} запросов` },
    { label: "Прогноз на месяц", value: formatUsd(spend.forecast_month), note: "по темпу последних 7 дней" },
    {
      label: "Токены за месяц",
      value: formatCompact(spend.tokens_in_month + spend.tokens_out_month),
      note: `вход ${formatCompact(spend.tokens_in_month)} · выход ${formatCompact(spend.tokens_out_month)}`,
    },
  ];

  return (
    <section aria-label="Расходы" className="flex h-full flex-col gap-2">
      <div className="flex-1 overflow-hidden rounded-xl bg-card shadow-xs ring-1 ring-foreground/10">
        <div className="grid h-full divide-y *:data-[slot=card]:rounded-none *:data-[slot=card]:ring-0 sm:grid-cols-2 sm:divide-y-0 sm:[&>*:nth-child(-n+2)]:border-b sm:[&>*:nth-child(odd)]:border-r">
          {kpis.map((kpi) => (
            <Card key={kpi.label} className="justify-between">
              <CardHeader>
                <CardTitle className="font-normal text-muted-foreground text-sm">{kpi.label}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                <div className="truncate text-2xl tabular-nums leading-none tracking-tight">{kpi.value}</div>
                <div className="truncate text-muted-foreground text-xs tabular-nums">{kpi.note}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
      {source === "backend" ? null : (
        <p className="text-muted-foreground text-xs">
          Расходы — демо-данные: OpenRouter не отдаёт расход по моделям для ключа, его будет считать бэкенд.
        </p>
      )}
    </section>
  );
}
