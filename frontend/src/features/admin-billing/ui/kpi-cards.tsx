import { Skeleton } from "@/components/ui/skeleton";
import { pluralizeRu } from "@/lib/plural";

import type { Currency, CurrencyKpis, PlatformTotals } from "../domain/contract";
import { formatInteger, formatMoney, formatMoneyCompact, formatPercent, formatPointsChange } from "../domain/format";
import { Kpi, RelativeTrend, Strong, Trend } from "./kpi-card";

const REFUND_WORDS = ["возврат", "возврата", "возвратов"] as const;

/** Money KPIs for the selected currency; churn is platform-wide because it doesn't depend on currency. */
export function KpiCards({
  currency,
  kpis,
  totals,
}: {
  currency: Currency;
  kpis: CurrencyKpis;
  totals: PlatformTotals;
}) {
  const money = (minor: number) => formatMoney(minor, currency);
  const churnDelta = totals.churn_rate - totals.churn_rate_prev;
  return (
    <section aria-label="Ключевые показатели" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <Kpi
        title="MRR"
        value={money(kpis.mrr_minor)}
        trend={<RelativeTrend current={kpis.mrr_minor} previous={kpis.mrr_prev_minor} polarity="up-good" />}
        footnote={
          <>
            ARR <Strong>{formatMoneyCompact(kpis.arr_minor, currency)}</Strong> · 30 дней назад{" "}
            {money(kpis.mrr_prev_minor)}
          </>
        }
      />
      <Kpi
        title="Выручка с начала месяца"
        value={money(kpis.revenue_month_minor)}
        trend={
          <RelativeTrend
            current={kpis.revenue_month_minor}
            previous={kpis.revenue_prev_month_to_date_minor}
            polarity="up-good"
          />
        }
        footnote={
          <>
            За те же дни прошлого месяца <Strong>{money(kpis.revenue_prev_month_to_date_minor)}</Strong>, за весь месяц{" "}
            {formatMoneyCompact(kpis.revenue_prev_month_minor, currency)}
          </>
        }
      />
      <Kpi
        title="Активные платные подписки"
        value={formatInteger(kpis.active_subscriptions)}
        trend={
          <RelativeTrend
            current={kpis.active_subscriptions}
            previous={kpis.active_subscriptions_prev}
            polarity="up-good"
          />
        }
        footnote={
          <>
            Во всех валютах <Strong>{formatInteger(totals.active_subscriptions)}</Strong>, ещё{" "}
            {formatInteger(totals.free_accounts)} на бесплатном тарифе
          </>
        }
      />
      <Kpi
        title="Отток за 30 дней, все валюты"
        value={formatPercent(totals.churn_rate)}
        trend={<Trend delta={churnDelta} label={formatPointsChange(churnDelta)} polarity="up-bad" />}
        footnote={
          <>
            Месяцем ранее <Strong>{formatPercent(totals.churn_rate_prev)}</Strong> платных подписок
          </>
        }
      />
      <Kpi
        title="ARPU"
        value={money(kpis.arpu_minor)}
        trend={<RelativeTrend current={kpis.arpu_minor} previous={kpis.arpu_prev_minor} polarity="up-good" />}
        footnote={
          <>
            MRR на платящий аккаунт · 30 дней назад <Strong>{money(kpis.arpu_prev_minor)}</Strong>
          </>
        }
      />
      <Kpi
        title="Возвраты в этом месяце"
        value={money(kpis.refunds_month_minor)}
        footnote={
          kpis.refunds_month_count === 0 ? (
            "Возвратов не было"
          ) : (
            <>
              <Strong>{formatInteger(kpis.refunds_month_count)}</Strong>{" "}
              {pluralizeRu(kpis.refunds_month_count, REFUND_WORDS)}
            </>
          )
        }
      />
    </section>
  );
}

export function KpiCardsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden="true">
      {["mrr", "revenue", "subscriptions", "churn", "arpu", "refunds"].map((key) => (
        <Skeleton key={key} className="h-32 rounded-xl" />
      ))}
    </div>
  );
}
