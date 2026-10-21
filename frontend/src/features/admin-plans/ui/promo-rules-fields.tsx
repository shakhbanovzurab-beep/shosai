"use client";

import type { ChangeEvent } from "react";

import { FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { businessZoneLabel, useBusinessZone } from "@/features/admin-sign-in/model/business-zone";

import type { BillingPeriodScope } from "../domain/contract";
import { type PromoTextKey, type PromoValues, promoInputId } from "../domain/promo-form-values";
import { Choice } from "./choice";
import { SwitchField, TextField } from "./form-field";

const PERIOD_OPTIONS: { value: BillingPeriodScope; label: string }[] = [
  { value: "both", label: "Месяц и год" },
  { value: "month", label: "Только месяц" },
  { value: "year", label: "Только год" },
];
const UNLIMITED = "Пусто — без ограничений.";

type RulesProps = {
  values: PromoValues;
  errors: Record<string, string>;
  disabled: boolean;
  onText: (key: PromoTextKey, value: string) => void;
  onPeriod: (period: BillingPeriodScope) => void;
  onFlag: (key: "first_payment_only" | "is_active", value: boolean) => void;
};

/** When and how often a code works: billing period, redemption limits, dates and switches. */
export function PromoRulesFields({ values, errors, disabled, onText, onPeriod, onFlag }: RulesProps) {
  const zone = businessZoneLabel(useBusinessZone());
  const text = (key: PromoTextKey) => ({
    id: promoInputId(key),
    value: values[key],
    error: errors[key],
    disabled,
    onChange: (event: ChangeEvent<HTMLInputElement>) => onText(key, event.target.value),
  });

  return (
    <>
      <FieldSet>
        <FieldLegend>Период оплаты</FieldLegend>
        <Choice
          name="promo-billing-period"
          label="Период оплаты"
          value={values.billing_period}
          options={PERIOD_OPTIONS}
          disabled={disabled}
          onChange={onPeriod}
        />
      </FieldSet>

      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Всего активаций"
            inputMode="numeric"
            placeholder="Без лимита"
            description={UNLIMITED}
            {...text("max_redemptions")}
          />
          <TextField
            label="Активаций на пользователя"
            inputMode="numeric"
            placeholder="Без лимита"
            description={UNLIMITED}
            {...text("per_user_limit")}
          />
          <TextField
            label="Действует с"
            type="date"
            description={`Дата по ${zone}. Пусто — сразу.`}
            {...text("valid_from")}
          />
          <TextField
            label="Действует по"
            type="date"
            description={`Включительно, дата по ${zone}. Пусто — бессрочно.`}
            {...text("valid_until")}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <SwitchField
            id="promo-first-payment-only"
            label="Только первый платёж"
            description="Скидка не повторяется при продлении."
            checked={values.first_payment_only}
            disabled={disabled}
            onCheckedChange={(checked) => onFlag("first_payment_only", checked)}
          />
          <SwitchField
            id="promo-is-active"
            label="Активен"
            description="Код можно ввести при оплате."
            checked={values.is_active}
            disabled={disabled}
            onCheckedChange={(checked) => onFlag("is_active", checked)}
          />
        </div>
      </FieldGroup>
    </>
  );
}
