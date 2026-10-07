import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { AiModel } from "../domain/contract";
import { formatPercent, formatUsd } from "../domain/format";

const TOP = 5;

type Row = { id: string; name: string; provider: string; spend: number };

export function TopModels({ models, total }: { models: AiModel[]; total: number }) {
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
  const max = rows[0]?.spend ?? 0;

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
