"use client";

import { X } from "lucide-react";

import { FilterSelect } from "@/components/filter-select";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { ERROR_PERIODS, ERROR_SEVERITIES, ERROR_SOURCES, type ErrorPeriod, ISSUE_STATUSES } from "../domain/dimensions";
import type { IssuesQuery } from "../domain/query";

type Props = {
  query: IssuesQuery;
  versions: string[];
  onChange: (patch: Partial<IssuesQuery>) => void;
};

export function ErrorsFilters({ query, versions, onChange }: Props) {
  const known = new Set(versions);
  const versionOptions = (query.version && !known.has(query.version) ? [query.version, ...versions] : versions).map(
    (version) => ({ id: version, label: version }),
  );
  const filtered = [query.source, query.severity, query.status, query.version, query.user].some(
    (value) => value !== null,
  );

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <FilterSelect
          allLabel="Все"
          label="Источник"
          value={query.source}
          options={ERROR_SOURCES}
          onChange={(source) => onChange({ source: source as IssuesQuery["source"] })}
        />
        <FilterSelect
          allLabel="Все"
          label="Уровень"
          value={query.severity}
          options={ERROR_SEVERITIES}
          onChange={(severity) => onChange({ severity: severity as IssuesQuery["severity"] })}
        />
        <FilterSelect
          allLabel="Все"
          label="Статус"
          value={query.status}
          options={ISSUE_STATUSES}
          onChange={(status) => onChange({ status: status as IssuesQuery["status"] })}
        />
        <FilterSelect
          allLabel="Все"
          label="Версия"
          value={query.version}
          options={versionOptions}
          onChange={(version) => onChange({ version })}
        />
        {query.user ? (
          <Button variant="secondary" size="sm" onClick={() => onChange({ user: null })}>
            <span className="text-muted-foreground">Пользователь:</span>
            {query.user}
            <X data-icon="inline-end" aria-label="Снять фильтр по пользователю" />
          </Button>
        ) : null}
        {filtered ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({ source: null, severity: null, status: null, version: null, user: null })}
          >
            Сбросить
          </Button>
        ) : null}
      </div>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={0}
        value={query.period}
        onValueChange={(period) => {
          if (period) onChange({ period: period as ErrorPeriod });
        }}
        aria-label="Период"
      >
        {ERROR_PERIODS.map((period) => (
          <ToggleGroupItem key={period.id} value={period.id} className="px-3">
            {period.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
