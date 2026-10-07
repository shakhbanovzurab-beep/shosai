"use client";

import { cn } from "cn";
import { TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";

import { CURRENCIES, CURRENCY_SYMBOL, type Plan, type PromoCode, type PromoStatus } from "../domain/contract";
import { formatPrices } from "../domain/format";
import { STATUS_LABEL } from "../domain/promo-labels";
import { scopeHealth } from "../domain/promo-scope";
import { STATUS_STYLES } from "./promo-status-styles";

export function StatusBadge({ status }: { status: PromoStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <Badge variant="outline" className={cn("gap-1.5 border px-2 py-1 font-medium", style.badgeClass)}>
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", style.dotClass)} />
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export function ScopeCell({ promo, plansById }: { promo: PromoCode; plansById: ReadonlyMap<string, Plan> }) {
  if (promo.scope === "all") return <Badge variant="secondary">Все тарифы</Badge>;
  const health = scopeHealth(promo, plansById);
  return (
    <div className="flex max-w-64 flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {promo.plan_ids.map((id) => {
          const plan = plansById.get(id);
          if (!plan) return null;
          return (
            <Badge
              key={id}
              variant="outline"
              className={plan.archived ? "text-muted-foreground line-through" : undefined}
              title={plan.archived ? `«${plan.name}» в архиве` : undefined}
            >
              {plan.name}
              {plan.archived ? <span className="sr-only"> (в архиве)</span> : null}
            </Badge>
          );
        })}
      </div>
      {health.kind === "none" ? (
        <span className="flex items-center gap-1 text-amber-600 text-xs dark:text-amber-400">
          <TriangleAlert aria-hidden="true" className="size-3.5 shrink-0" />
          Нет доступных тарифов — код не применится
        </span>
      ) : null}
      {health.kind === "partial" ? (
        <span className="flex items-center gap-1 text-muted-foreground text-xs">
          <TriangleAlert aria-hidden="true" className="size-3.5 shrink-0 text-amber-500" />
          Часть тарифов в архиве: {health.unavailable}
        </span>
      ) : null}
    </div>
  );
}

/** A percent, or the fixed amount in each currency it applies to — and which currencies it doesn't. */
export function DiscountCell({ promo }: { promo: PromoCode }) {
  if (promo.discount_type === "percent")
    return <span className="font-medium tabular-nums">−{promo.percent_off}% · любая валюта</span>;
  const missing = CURRENCIES.filter((c) => promo.amounts_off[c] === undefined);
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-medium tabular-nums">−{formatPrices(promo.amounts_off)}</span>
      {missing.length > 0 ? (
        <span className="text-muted-foreground text-xs">
          Не действует в: {missing.map((c) => CURRENCY_SYMBOL[c]).join(", ")}
        </span>
      ) : null}
    </div>
  );
}
