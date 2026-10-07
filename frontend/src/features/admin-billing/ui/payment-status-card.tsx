import { cn } from "cn";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { Currency, StatusSummary } from "../domain/contract";
import { formatInteger, formatMoney, formatPercent } from "../domain/format";
import { STATUS_LABELS } from "../domain/labels";
import { STATUS_STYLES } from "./status-styles";

export function PaymentStatusCard({ currency, summary }: { currency: Currency; summary: StatusSummary[] }) {
  const total = summary.reduce((sum, row) => sum + row.count, 0);
  const settled = summary.find((row) => row.status === "paid")?.count ?? 0;
  const failed = summary.find((row) => row.status === "failed")?.count ?? 0;
  const attempted = settled + failed;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Платежи по статусам</CardTitle>
        <CardDescription>
          За 30 дней · успешных списаний{" "}
          <span className="font-medium text-foreground tabular-nums">
            {attempted === 0 ? "—" : formatPercent(settled / attempted)}
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {total === 0 ? (
          <p className="text-muted-foreground text-sm">За последние 30 дней платежей не было.</p>
        ) : (
          <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
            {summary.map((row) =>
              row.count === 0 ? null : (
                <div
                  key={row.status}
                  className={cn("h-full first:rounded-l-full last:rounded-r-full", STATUS_STYLES[row.status].swatch)}
                  style={{ width: `${(row.count / total) * 100}%` }}
                />
              ),
            )}
          </div>
        )}
        <ul className="flex flex-col divide-y divide-border/60">
          {summary.map((row) => {
            const { icon: Icon, swatch } = STATUS_STYLES[row.status];
            return (
              <li key={row.status} className="flex items-center gap-3 py-2 text-sm first:pt-0 last:pb-0">
                <span className={cn("size-2.5 shrink-0 rounded-[2px]", swatch)} aria-hidden="true" />
                <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{STATUS_LABELS[row.status]}</span>
                <span className="text-muted-foreground tabular-nums">{formatInteger(row.count)}</span>
                <span className="w-28 text-right font-medium tabular-nums">
                  {formatMoney(row.amount_minor, currency)}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="text-muted-foreground text-xs">Для возвратов указана возвращённая сумма.</p>
      </CardContent>
    </Card>
  );
}
