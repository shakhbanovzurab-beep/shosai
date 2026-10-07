import { cn } from "cn";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { Currency, CurrencyOverview } from "../domain/contract";
import { CURRENCY_NAMES, CURRENCY_SYMBOLS, formatInteger, formatMoney, formatPercent } from "../domain/format";

/** MRR, revenue and subscriptions side by side per currency, each in its own money; nothing is converted. */
export function CurrencyBreakdown({
  currencies,
  selected,
  onSelect,
}: {
  currencies: CurrencyOverview[];
  selected: Currency;
  onSelect: (currency: Currency) => void;
}) {
  const subscriptions = currencies.reduce((sum, entry) => sum + entry.kpis.active_subscriptions, 0);
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>По валютам</CardTitle>
        <CardDescription>Суммы в разных валютах не складываются и не пересчитываются по курсу.</CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <Table className="min-w-[36rem] **:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4">
          <TableHeader>
            <TableRow>
              <TableHead className="font-normal">Валюта</TableHead>
              <TableHead className="text-right font-normal">MRR</TableHead>
              <TableHead className="text-right font-normal">С начала месяца</TableHead>
              <TableHead className="text-right font-normal">Подписки</TableHead>
              <TableHead className="text-right font-normal">Доля</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currencies.map(({ currency, kpis }) => (
              <TableRow
                key={currency}
                className={cn("border-border/60", currency === selected && "bg-muted/50")}
                data-state={currency === selected ? "selected" : undefined}
              >
                <TableCell>
                  <Button
                    variant="link"
                    className="h-auto p-0 font-medium"
                    aria-pressed={currency === selected}
                    onClick={() => onSelect(currency)}
                  >
                    <span aria-hidden="true" className="w-4 text-muted-foreground">
                      {CURRENCY_SYMBOLS[currency]}
                    </span>
                    {CURRENCY_NAMES[currency]}
                  </Button>
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(kpis.mrr_minor, currency)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatMoney(kpis.revenue_month_minor, currency)}
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatInteger(kpis.active_subscriptions)}</TableCell>
                <TableCell className="text-right text-muted-foreground tabular-nums">
                  {subscriptions === 0 ? "—" : formatPercent(kpis.active_subscriptions / subscriptions)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
