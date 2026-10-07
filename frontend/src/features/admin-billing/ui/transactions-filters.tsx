"use client";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { CURRENCIES, PERIODS, TRANSACTION_STATUSES, type TransactionsQuery } from "../domain/contract";
import { CURRENCY_NAMES } from "../domain/format";
import { PERIOD_LABELS, STATUS_LABELS } from "../domain/labels";
import { DEFAULT_PERIOD } from "../domain/query";

const ALL = "all";

function FilterSelect<T extends string>({
  label,
  value,
  options,
  labels,
  allLabel,
  onChange,
}: {
  label: string;
  value: T | undefined;
  options: readonly T[];
  labels: Record<T, string>;
  /** Adds an "all" option that clears the filter. */
  allLabel?: string;
  onChange: (value: T | undefined) => void;
}) {
  return (
    <Select value={value ?? ALL} onValueChange={(next) => onChange(options.find((option) => option === next))}>
      <SelectTrigger size="sm" aria-label={label}>
        <span className="text-muted-foreground">{label}:</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent position="popper" align="end">
        <SelectGroup>
          {allLabel ? <SelectItem value={ALL}>{allLabel}</SelectItem> : null}
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {labels[option]}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

/** Status, period and currency filters; any change goes back to the first page. */
export function TransactionsFilters({
  query,
  onChange,
}: {
  query: TransactionsQuery;
  onChange: (query: TransactionsQuery) => void;
}) {
  return (
    <>
      <FilterSelect
        label="Статус"
        value={query.status}
        options={TRANSACTION_STATUSES}
        labels={STATUS_LABELS}
        allLabel="Все"
        onChange={(status) => onChange({ ...query, status, page: 1 })}
      />
      <FilterSelect
        label="Период"
        value={query.period}
        options={PERIODS}
        labels={PERIOD_LABELS}
        onChange={(period) => onChange({ ...query, period: period ?? DEFAULT_PERIOD, page: 1 })}
      />
      <FilterSelect
        label="Валюта"
        value={query.currency}
        options={CURRENCIES}
        labels={CURRENCY_NAMES}
        allLabel="Все"
        onChange={(currency) => onChange({ ...query, currency, page: 1 })}
      />
    </>
  );
}
