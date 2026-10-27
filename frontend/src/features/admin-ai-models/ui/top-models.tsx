import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { AiModel, SpendSummary } from "../domain/contract";
import { formatPercent, formatUsd } from "../domain/format";

const TOP = 5;

type Row = { id: string; name: string; provider: string; spend: number };

/** Топ моделей каталога за месяц; расход вне каталога — распознавание, документы, Jev — отдельной строкой. */
export function TopModels({ models, spend }: { models: AiModel[]; spend: SpendSummary }) {
  const total = spend.month;
  const outside = spend.outside_catalogue;
  const spending = models.filter((model) => model.month_spend > 0).toSorted((a, b) => b.month_spend - a.month_spend);
  const rows: Row[] = spending
    .slice(0, TOP)
    .map((model) => ({ id: model.id, name: model.name, provider: model.provider, spend: model.month_spend }));
  const rest = spending.slice(TOP);
  if (rest.length > 0)
    rows.push({
      id: "other",
      name: "Остальные",
      provider: `${rest.length} мод.`,
      spend: rest.reduce((sum, model) => sum + model.month_spend, 0),
    });
  if (outside.spend > 0)
    rows.push({ id: "outside", name: "Вне каталога", provider: "речь, документы, Jev", spend: outside.spend });
  const max = Math.max(0, ...rows.map((row) => row.spend));

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="font-normal">Топ моделей по расходам</CardTitle>
        <CardDescription>С начала месяца</CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="py-10 text-center text-muted-foreground text-sm">В этом месяце расходов пока нет.</p>
        ) : (
          <ol className="flex flex-col gap-4">
            {rows.map((row) => (
              <li key={row.id} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate">
                    {row.name} <span className="text-muted-foreground text-xs">{row.provider}</span>
                  </span>
                  <span className="shrink-0 tabular-nums">
                    {formatUsd(row.spend)}{" "}
                    <span className="text-muted-foreground text-xs">
                      {total > 0 ? formatPercent(row.spend / total) : ""}
                    </span>
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                  <div
                    className="h-full rounded-full bg-chart-2"
                    style={{ width: `${max > 0 ? (row.spend / max) * 100 : 0}%` }}
                  />
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
