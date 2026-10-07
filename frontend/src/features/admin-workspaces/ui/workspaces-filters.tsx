"use client";

import { Search } from "lucide-react";

import { FilterSelect } from "@/components/filter-select";
import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import type { WorkspaceStatus } from "../domain/contract";
import { STATUS_OPTIONS } from "../domain/labels";
import { DEFAULT_FILTER, SORTS, type WorkspaceFilter, type WorkspaceSort } from "../domain/list";

type Props = { filter: WorkspaceFilter; plans: string[]; onChange: (filter: WorkspaceFilter) => void };

/** Search by name, slug or owner; narrow by status and plan; choose the order. */
export function WorkspacesFilters({ filter, plans, onChange }: Props) {
  const filtered = filter.q !== "" || filter.status !== null || filter.plan !== null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <InputGroup className="h-8 w-64 max-w-full">
          <InputGroupAddon>
            <Search aria-hidden="true" />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            value={filter.q}
            onChange={(event) => onChange({ ...filter, q: event.target.value })}
            placeholder="Название, адрес или владелец"
            aria-label="Поиск пространств"
          />
        </InputGroup>
        <FilterSelect
          allLabel="Все"
          label="Статус"
          value={filter.status}
          options={STATUS_OPTIONS}
          onChange={(status) => onChange({ ...filter, status: status as WorkspaceStatus | null })}
        />
        <FilterSelect
          allLabel="Все"
          label="Тариф"
          value={filter.plan}
          options={plans.map((plan) => ({ id: plan, label: plan }))}
          onChange={(plan) => onChange({ ...filter, plan })}
        />
        {filtered ? (
          <Button variant="ghost" size="sm" onClick={() => onChange({ ...DEFAULT_FILTER, sort: filter.sort })}>
            Сбросить
          </Button>
        ) : null}
      </div>
      <Select value={filter.sort} onValueChange={(sort) => onChange({ ...filter, sort: sort as WorkspaceSort })}>
        <SelectTrigger size="sm" aria-label="Порядок">
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper" align="end">
          <SelectGroup>
            {SORTS.map((sort) => (
              <SelectItem key={sort.id} value={sort.id}>
                {sort.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}
