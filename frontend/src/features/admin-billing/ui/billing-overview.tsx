"use client";

import { useState } from "react";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { Currency } from "../domain/contract";
import { overviewResource } from "../model/billing-store";
import { BillingState } from "./billing-state";
import { CurrencyBreakdown } from "./currency-breakdown";
import { CurrencySwitcher } from "./currency-switcher";
import { KpiCards, KpiCardsSkeleton } from "./kpi-cards";
import { PaymentStatusCard } from "./payment-status-card";
import { PayoutsCard } from "./payouts-card";

// Recharts is heavy; load it after the KPIs, behind a placeholder of the same size.
const RevenueChart = dynamic(() => import("./revenue-chart").then((module) => module.RevenueChart), {
  loading: () => <Skeleton className="h-96 rounded-xl" />,
});

const retry = () => void overviewResource.refresh();

const overviewSkeleton = (
  <div className="flex flex-col gap-4" aria-busy="true">
    <span className="sr-only">Загружаем показатели…</span>
    <Skeleton className="h-8 w-40 self-end rounded-lg" />
    <KpiCardsSkeleton />
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <Skeleton className="h-96 rounded-xl xl:col-span-8" />
      <Skeleton className="h-96 rounded-xl xl:col-span-4" />
    </div>
  </div>
);

/** KPIs, the revenue chart, status summary, currency breakdown and payouts from GET /api/admin/billing/overview. */
export function BillingOverview() {
  const state = usePollingResource(overviewResource);
  const [currency, setCurrency] = useState<Currency>("RUB");

  return (
    <BillingState
      state={state}
      fallback={overviewSkeleton}
      errorTitle="Не удалось загрузить показатели"
      onRetry={retry}
    >
      {(overview) => {
        const selected = overview.by_currency.find((entry) => entry.currency === currency) ?? overview.by_currency[0];
        if (!selected) return null;
        return (
          <div className="flex flex-col gap-4">
            <div className="flex justify-end">
              <CurrencySwitcher value={selected.currency} onChange={setCurrency} />
            </div>
            <KpiCards currency={selected.currency} kpis={selected.kpis} totals={overview.totals} />
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
              <div className="xl:col-span-8">
                <RevenueChart currency={selected.currency} months={selected.revenue_by_month} />
              </div>
              <div className="xl:col-span-4">
                <PaymentStatusCard currency={selected.currency} summary={selected.payments_by_status} />
              </div>
              <div className="xl:col-span-8">
                <CurrencyBreakdown
                  currencies={overview.by_currency}
                  selected={selected.currency}
                  onSelect={setCurrency}
                />
              </div>
              <div className="xl:col-span-4">
                <PayoutsCard currency={selected.currency} payouts={selected.payouts} />
              </div>
            </div>
          </div>
        );
      }}
    </BillingState>
  );
}
