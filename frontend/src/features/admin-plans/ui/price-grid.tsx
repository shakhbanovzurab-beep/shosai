"use client";

import { Fragment } from "react";

import { FieldDescription, FieldError, FieldLegend, FieldSet } from "@/components/ui/field";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";

import { CURRENCIES, CURRENCY_NAME, CURRENCY_SYMBOL, type Currency } from "../domain/contract";
import type { PlanValues, PricePeriod } from "../domain/plan-form-values";
import { planInputId } from "../domain/plan-form-values";

const PERIODS: { key: PricePeriod; label: string }[] = [
  { key: "price_monthly", label: "В месяц" },
  { key: "price_yearly", label: "В год" },
];

type PriceGridProps = {
  values: PlanValues;
  errors: Record<string, string>;
  hint: string;
  disabled: boolean;
  onChange: (period: PricePeriod, currency: Currency, value: string) => void;
};

/** Monthly and yearly prices in every currency: one row per period, one column per currency. */
export function PriceGrid({ values, errors, hint, disabled, onChange }: PriceGridProps) {
  const messages = PERIODS.flatMap(({ key }) =>
    CURRENCIES.flatMap((c) => {
      const message = errors[`${key}.${c}`];
      return message ? [{ id: `${planInputId(`${key}.${c}`)}-error`, message }] : [];
    }),
  );
  return (
    <FieldSet>
      <FieldLegend>Цена</FieldLegend>
      <div className="grid grid-cols-[auto_repeat(3,minmax(0,1fr))] items-center gap-2">
        <span aria-hidden="true" />
        {CURRENCIES.map((c) => (
          <span key={c} className="text-muted-foreground text-xs">
            {CURRENCY_NAME[c]}
          </span>
        ))}
        {PERIODS.map(({ key, label }) => (
          <Fragment key={key}>
            <span className="pe-2 text-sm">{label}</span>
            {CURRENCIES.map((c) => {
              const id = planInputId(`${key}.${c}`);
              const error = errors[`${key}.${c}`];
              return (
                <InputGroup key={c}>
                  <InputGroupInput
                    id={id}
                    aria-label={`${label}, ${CURRENCY_NAME[c].toLowerCase()}`}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? `${id}-error` : "plan-price-hint"}
                    inputMode="decimal"
                    autoComplete="off"
                    disabled={disabled}
                    value={values[key][c]}
                    onChange={(event) => onChange(key, c, event.target.value)}
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupText>{CURRENCY_SYMBOL[c]}</InputGroupText>
                  </InputGroupAddon>
                </InputGroup>
              );
            })}
          </Fragment>
        ))}
      </div>
      <FieldDescription id="plan-price-hint">{hint}</FieldDescription>
      {messages.map(({ id, message }) => (
        <FieldError key={id} id={id}>
          {message}
        </FieldError>
      ))}
    </FieldSet>
  );
}
