"use client";

import { useState } from "react";

import { Plus, Search, TicketPercent } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import type { Plan, PromoCode, PromoStatus } from "../domain/contract";
import { formatInteger } from "../domain/format";
import { STATUS_LABEL } from "../domain/promo-labels";
import { PromoTable } from "./promo-table";

type StatusFilter = PromoStatus | "all";
const STATUS_FILTERS = Object.keys(STATUS_LABEL) as PromoStatus[];

const isStatusFilter = (value: string): value is StatusFilter => value === "all" || value in STATUS_LABEL;

function NoPromos({ onCreate }: { onCreate: () => void }) {
  return (
    <Empty className="border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <TicketPercent />
        </EmptyMedia>
        <EmptyTitle>Промокодов пока нет</EmptyTitle>
        <EmptyDescription>Создайте код со скидкой на все тарифы или только на выбранные.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button size="sm" onClick={onCreate}>
          <Plus data-icon="inline-start" />
          Новый промокод
        </Button>
      </EmptyContent>
    </Empty>
  );
}

export function PromoList({
  promos,
  plans,
  onCreate,
  onEdit,
  onCopy,
  onRemove,
}: {
  promos: PromoCode[];
  plans: Plan[];
  onCreate: () => void;
  onEdit: (promo: PromoCode) => void;
  onCopy: (promo: PromoCode) => void;
  onRemove: (promo: PromoCode) => void;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");

  if (promos.length === 0) return <NoPromos onCreate={onCreate} />;

  const plansById = new Map(plans.map((plan) => [plan.id, plan]));
  const needle = query.trim().toUpperCase();
  const visible = promos.filter(
    (promo) => (status === "all" || promo.status === status) && (needle === "" || promo.code.includes(needle)),
  );

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <InputGroup className="w-full sm:w-64">
          <InputGroupAddon>
            <Search aria-hidden="true" />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            aria-label="Поиск по коду"
            placeholder="Поиск по коду…"
            autoComplete="off"
            spellCheck={false}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </InputGroup>
        <Select value={status} onValueChange={(value) => (isStatusFilter(value) ? setStatus(value) : undefined)}>
          <SelectTrigger size="sm" aria-label="Фильтр по статусу">
            <span className="text-muted-foreground">Статус:</span>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">Все</SelectItem>
              {STATUS_FILTERS.map((value) => (
                <SelectItem key={value} value={value}>
                  {STATUS_LABEL[value]}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <span className="text-muted-foreground text-sm" aria-live="polite">
          Показано {formatInteger(visible.length)} из {formatInteger(promos.length)}
        </span>
      </div>
      {visible.length > 0 ? (
        <PromoTable promos={visible} plansById={plansById} onEdit={onEdit} onCopy={onCopy} onRemove={onRemove} />
      ) : (
        <Empty className="border border-dashed">
          <EmptyHeader>
            <EmptyTitle>Ничего не найдено</EmptyTitle>
            <EmptyDescription>Измените запрос или фильтр по статусу.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setQuery("");
                setStatus("all");
              }}
            >
              Сбросить фильтры
            </Button>
          </EmptyContent>
        </Empty>
      )}
    </>
  );
}
