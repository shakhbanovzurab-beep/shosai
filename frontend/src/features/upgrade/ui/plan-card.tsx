"use client";

import { useState } from "react";

import { cn } from "cn";
import { Check, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import type { Plan, PlanId } from "../domain/contract";
import { planHighlights } from "../domain/plan-features";
import { PlanAction } from "./plan-action";
import { SeatPicker } from "./seat-picker";
import { usePlanFormat } from "./use-plan-format";
import { usePlanWords } from "./use-plan-words";

function Price({ plan, seats }: { plan: Plan; seats: number | null }) {
  const t = useTranslations("upgrade");
  const { price } = usePlanFormat();
  if (!plan.price) {
    return (
      <div className="flex flex-col gap-1">
        <span className="font-semibold text-4xl tracking-tight">{t("card.custom")}</span>
        <span className="text-muted-foreground text-sm">{t("card.tailored")}</span>
      </div>
    );
  }
  // Prices are always per month (`interval: "month"`), the only interval the contract has.
  const { amount_cents: cents, currency } = plan.price;
  let note = t("card.billedMonthly");
  if (cents === 0) note = t("card.freeForever");
  else if (seats !== null) note = t("card.seatsTotal", { total: price(cents * seats, currency), seats });
  return (
    <div className="flex flex-col gap-1">
      <span className="flex items-baseline gap-1">
        <span className="font-semibold text-4xl tracking-tight">{price(cents, currency)}</span>
        <span className="text-muted-foreground text-sm">
          {seats === null ? t("card.perMonth") : t("card.perUserPerMonth")}
        </span>
      </span>
      <span className="text-muted-foreground text-sm tabular-nums">{note}</span>
    </div>
  );
}

type PlanCardProps = { plan: Plan; plans: Plan[]; currentPlanId: PlanId };

export function PlanCard({ plan, plans, currentPlanId }: PlanCardProps) {
  const t = useTranslations("upgrade");
  const words = usePlanWords();
  const current = plan.id === currentPlanId;
  const titleId = `plan-${plan.id}`;
  const [seats, setSeats] = useState(plan.seats?.min ?? 1);
  const previous = plans[plans.findIndex((p) => p.id === plan.id) - 1];
  const perSeat = plan.seats && plan.price ? plan.seats : null;

  return (
    <Card
      aria-labelledby={titleId}
      className={cn("gap-6 px-6 py-6", plan.highlighted && "shadow-md ring-2 ring-primary")}
    >
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <h2 id={titleId} className="font-semibold text-lg">
            {plan.name}
          </h2>
          {current ? <Badge variant="secondary">{t("card.yourPlan")}</Badge> : null}
          {!current && plan.highlighted ? <Badge>{t("card.recommended")}</Badge> : null}
        </div>
        <p className="text-muted-foreground text-sm" dir="auto">
          {plan.tagline}
        </p>
      </div>
      <Price plan={plan} seats={perSeat ? seats : null} />
      {perSeat && !current ? (
        <SeatPicker id={`${titleId}-seats`} value={seats} min={perSeat.min} max={perSeat.max} onChange={setSeats} />
      ) : null}
      <PlanAction plan={plan} plans={plans} currentPlanId={currentPlanId} seats={perSeat ? seats : undefined} />
      <Separator />
      <ul className="flex flex-col gap-3 text-sm">
        {planHighlights(plan, previous).map((item) => {
          const label = words.highlight(item);
          return (
            <li key={label} className={cn("flex items-start gap-2.5", !item.included && "text-muted-foreground")}>
              {item.included ? (
                <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              ) : (
                <X className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              )}
              {item.included ? (
                <span dir={item.kind === "custom" ? "auto" : undefined}>{label}</span>
              ) : (
                <span>
                  <span aria-hidden="true">{label}</span>
                  <span className="sr-only">{t("card.notIncluded", { item: label })}</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
