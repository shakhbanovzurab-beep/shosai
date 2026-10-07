"use client";

import { Copy, MoreHorizontal, Pencil, Power, PowerOff, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { Plan, PromoCode } from "../domain/contract";
import { formatInteger, validity } from "../domain/format";
import { PERIOD_LABEL } from "../domain/promo-labels";
import { setPromoActive } from "../model/promo-actions";
import { DiscountCell, ScopeCell, StatusBadge } from "./promo-cells";

type RowActions = {
  onEdit: (promo: PromoCode) => void;
  onCopy: (promo: PromoCode) => void;
  onRemove: (promo: PromoCode) => void;
};

function PromoRowMenu({ promo, onEdit, onCopy, onRemove }: { promo: PromoCode } & RowActions) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Действия с промокодом ${promo.code}`}>
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => onEdit(promo)}>
          <Pencil />
          Редактировать
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onCopy(promo)}>
          <Copy />
          Дублировать
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void setPromoActive(promo, !promo.is_active)}>
          {promo.is_active ? <PowerOff /> : <Power />}
          {promo.is_active ? "Отключить" : "Включить"}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onSelect={() => onRemove(promo)}>
          <Trash2 />
          Удалить
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function PromoRow({
  promo,
  plansById,
  ...actions
}: { promo: PromoCode; plansById: ReadonlyMap<string, Plan> } & RowActions) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-col items-start gap-1">
          <span className="font-medium font-mono">{promo.code}</span>
          {promo.first_payment_only ? (
            <span className="text-muted-foreground text-xs">Только первый платёж</span>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="whitespace-nowrap">
        <DiscountCell promo={promo} />
      </TableCell>
      <TableCell>
        <ScopeCell promo={promo} plansById={plansById} />
      </TableCell>
      <TableCell className="whitespace-nowrap">{PERIOD_LABEL[promo.billing_period]}</TableCell>
      <TableCell className="whitespace-nowrap">
        <div className="flex flex-col gap-0.5">
          <span className="tabular-nums">
            {formatInteger(promo.redemptions)} /{" "}
            {promo.max_redemptions === null ? "∞" : formatInteger(promo.max_redemptions)}
            {promo.max_redemptions === null ? <span className="sr-only"> (без лимита)</span> : null}
          </span>
          <span className="text-muted-foreground text-xs">
            {promo.per_user_limit === null
              ? "Без лимита на пользователя"
              : `До ${promo.per_user_limit} на пользователя`}
          </span>
        </div>
      </TableCell>
      <TableCell className="whitespace-nowrap text-muted-foreground">{validity(promo)}</TableCell>
      <TableCell>
        <StatusBadge status={promo.status} />
      </TableCell>
      <TableCell className="w-10 text-right">
        <PromoRowMenu promo={promo} {...actions} />
      </TableCell>
    </TableRow>
  );
}

export function PromoTable({
  promos,
  plansById,
  ...actions
}: { promos: PromoCode[]; plansById: ReadonlyMap<string, Plan> } & RowActions) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table className="**:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4">
        <TableHeader className="bg-muted/40">
          <TableRow>
            <TableHead>Код</TableHead>
            <TableHead>Скидка</TableHead>
            <TableHead>Тарифы</TableHead>
            <TableHead>Период</TableHead>
            <TableHead>Активации</TableHead>
            <TableHead>Срок действия</TableHead>
            <TableHead>Статус</TableHead>
            <TableHead className="w-10">
              <span className="sr-only">Действия</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {promos.map((promo) => (
            <PromoRow key={promo.id} promo={promo} plansById={plansById} {...actions} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
