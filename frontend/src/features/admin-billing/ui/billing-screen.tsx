import { Suspense } from "react";

import { BillingOverview } from "./billing-overview";
import { TransactionsCard, TransactionsCardSkeleton } from "./transactions-card";

export function BillingScreen() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl tracking-tight">Финансы и биллинг</h1>
        <p className="text-muted-foreground text-sm">
          Подписки, выручка и платежи всех клиентов Leo. Суммы в рублях, даты в UTC.
        </p>
      </div>
      <BillingOverview />
      {/* The table reads its filters from the URL, which is only known in the browser. */}
      <Suspense fallback={<TransactionsCardSkeleton />}>
        <TransactionsCard />
      </Suspense>
    </div>
  );
}
