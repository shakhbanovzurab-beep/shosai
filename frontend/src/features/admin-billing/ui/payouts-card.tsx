import { Landmark } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { Currency, Payouts } from "../domain/contract";
import { formatDay, formatDayMonth, formatMoney } from "../domain/format";
import { PAYOUT_STATUS_LABELS } from "../domain/labels";

export function PayoutsCard({ currency, payouts }: { currency: Currency; payouts: Payouts }) {
  const { next } = payouts;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Выплаты</CardTitle>
        <CardDescription className="truncate">
          {payouts.provider} → {payouts.account}
        </CardDescription>
        <CardAction>
          <Landmark className="size-4 text-muted-foreground" aria-hidden="true" />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1 rounded-lg border border-border/60 p-3">
          <span className="text-muted-foreground text-xs">Следующая выплата</span>
          {next ? (
            <>
              <span className="font-medium text-2xl tabular-nums leading-tight">
                {formatMoney(next.amount_minor, currency)}
              </span>
              <span className="text-muted-foreground text-sm">
                {formatDayMonth(next.date)} · комиссия {formatMoney(next.fee_minor, currency)}
              </span>
            </>
          ) : (
            <span className="text-sm">Пока нечего выплачивать — новые платежи попадут в следующую выплату.</span>
          )}
        </div>
        {payouts.recent.length > 0 ? (
          <ul className="flex flex-col divide-y divide-border/60" aria-label="Последние выплаты">
            {payouts.recent.map((payout) => (
              <li key={payout.id} className="flex items-center gap-3 py-2 text-sm first:pt-0 last:pb-0">
                <span className="min-w-0 flex-1 truncate text-muted-foreground">{formatDay(payout.date)}</span>
                {payout.status === "paid" ? null : (
                  <Badge variant="secondary" className="rounded-md">
                    {PAYOUT_STATUS_LABELS[payout.status]}
                  </Badge>
                )}
                <span className="font-medium tabular-nums">{formatMoney(payout.amount_minor, currency)}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <p className="text-muted-foreground text-xs">
          Платежи картой и через СБП зачисляются по рабочим дням, переводы по счёту — сразу на счёт.
        </p>
      </CardContent>
    </Card>
  );
}
