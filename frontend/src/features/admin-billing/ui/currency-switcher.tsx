"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { CURRENCIES, type Currency } from "../domain/contract";
import { CURRENCY_NAMES, CURRENCY_SYMBOLS } from "../domain/format";
import { isCurrency } from "../domain/query";

/** Picks which currency the money KPIs, chart and payouts are shown in. */
export function CurrencySwitcher({ value, onChange }: { value: Currency; onChange: (currency: Currency) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span id="billing-currency-label" className="text-muted-foreground text-sm">
        Валюта
      </span>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={0}
        value={value}
        aria-labelledby="billing-currency-label"
        onValueChange={(next) => {
          // Radix sends "" when the active item is pressed again; keep the current currency then.
          if (isCurrency(next)) onChange(next);
        }}
      >
        {CURRENCIES.map((currency) => (
          <ToggleGroupItem key={currency} value={currency} aria-label={CURRENCY_NAMES[currency]} className="min-w-10">
            {CURRENCY_SYMBOLS[currency]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
