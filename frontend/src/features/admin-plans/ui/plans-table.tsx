"use client";

import { Archive, ArchiveRestore, MoreHorizontal, Pencil, Star, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { pluralizeRu } from "@/lib/plural";

import { CURRENCIES, PLAN_AUDIENCE_LABEL, PLAN_CAPABILITIES, type Plan } from "../domain/contract";
import { formatInteger, formatPrices } from "../domain/format";
import { restorePlan, setPlanActive } from "../model/plan-actions";

/** "120 мин", "без лимита", "нет"; on a custom-priced plan a limit is the starting point: "от 250 ГБ". */
function limitText(value: number | null, unit: string, custom: boolean) {
  if (value === null) return "без лимита";
  if (value === 0) return "нет";
  return `${custom ? "от " : ""}${unit === "МБ" && value % 1024 === 0 ? `${formatInteger(value / 1024)} ГБ` : `${formatInteger(value)} ${unit}`}`;
}

function LimitsCell({ plan }: { plan: Plan }) {
  const { limits, capabilities, custom_pricing: custom } = plan;
  const extras = PLAN_CAPABILITIES.filter((c) => capabilities[c]).length;
  return (
    <div className="flex flex-col gap-0.5 text-xs">
      <span>Встречи: {limitText(limits.meeting_minutes_per_month, "мин/мес", false)}</span>
      <span className="text-muted-foreground">
        Файлы: {limitText(limits.file_manager_gb, "ГБ", custom)} · База знаний:{" "}
        {limitText(limits.knowledge_base_mb, "МБ", custom)}
      </span>
      {extras > 0 ? (
        <span className="text-muted-foreground">
          + {extras} {pluralizeRu(extras, ["возможность", "возможности", "возможностей"])} для команд
        </span>
      ) : null}
    </div>
  );
}

function PriceCell({ plan }: { plan: Plan }) {
  if (plan.custom_pricing) return <span>По договорённости</span>;
  const free = CURRENCIES.every((c) => plan.price_monthly[c] === 0 && plan.price_yearly[c] === 0);
  if (free) return <span>Бесплатно</span>;
  const unit = plan.seats ? " за польз." : "";
  return (
    <div className="flex flex-col gap-0.5 whitespace-nowrap tabular-nums">
      <span>
        {formatPrices(plan.price_monthly)} / мес{unit}
      </span>
      <span className="text-muted-foreground text-xs">
        {formatPrices(plan.price_yearly)} / год{unit}
      </span>
    </div>
  );
}

type RowProps = { plan: Plan; onEdit: (plan: Plan) => void; onRemove: (plan: Plan) => void };

function PlanRowMenu({ plan, onEdit, onRemove }: RowProps) {
  const archivable = plan.subscribers > 0;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Действия с тарифом «${plan.name}»`}>
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {plan.archived ? (
          <DropdownMenuItem onSelect={() => void restorePlan(plan)}>
            <ArchiveRestore />
            Восстановить
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onSelect={() => onEdit(plan)}>
            <Pencil />
            Редактировать
          </DropdownMenuItem>
        )}
        {plan.archived && archivable ? null : (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => onRemove(plan)}>
              {archivable ? <Archive /> : <Trash2 />}
              {archivable ? "В архив" : "Удалить"}
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function PlanRow({ plan, onEdit, onRemove }: RowProps) {
  return (
    <TableRow className={plan.archived ? "bg-muted/30" : undefined}>
      <TableCell className="min-w-56">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{plan.name}</span>
            {plan.is_featured ? (
              <Badge variant="secondary">
                <Star data-icon="inline-start" />
                Рекомендуемый
              </Badge>
            ) : null}
            {plan.archived ? <Badge variant="outline">В архиве</Badge> : null}
          </div>
          <span className="text-muted-foreground text-xs">
            <span className="font-mono">{plan.slug}</span> · {PLAN_AUDIENCE_LABEL[plan.audience]}
            {plan.seats ? `, ${plan.seats.min}–${plan.seats.max ?? "∞"} польз.` : null}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <PriceCell plan={plan} />
      </TableCell>
      <TableCell className="min-w-56">
        <LimitsCell plan={plan} />
      </TableCell>
      <TableCell className="text-right tabular-nums">{formatInteger(plan.subscribers)}</TableCell>
      <TableCell className="text-right text-muted-foreground tabular-nums">{plan.sort_order}</TableCell>
      <TableCell>
        <Switch
          checked={plan.is_active}
          disabled={plan.archived}
          onCheckedChange={(checked) => void setPlanActive(plan, checked)}
          aria-label={`Тариф «${plan.name}» активен`}
        />
      </TableCell>
      <TableCell className="w-10 text-right">
        <PlanRowMenu plan={plan} onEdit={onEdit} onRemove={onRemove} />
      </TableCell>
    </TableRow>
  );
}

export function PlansTable({ plans, onEdit, onRemove }: { plans: Plan[] } & Omit<RowProps, "plan">) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table className="**:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4">
        <TableHeader className="bg-muted/40">
          <TableRow>
            <TableHead>Тариф</TableHead>
            <TableHead>Цена</TableHead>
            <TableHead>Лимиты</TableHead>
            <TableHead className="text-right">Подписчики</TableHead>
            <TableHead className="text-right">Порядок</TableHead>
            <TableHead>Активен</TableHead>
            <TableHead className="w-10">
              <span className="sr-only">Действия</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {plans.map((plan) => (
            <PlanRow key={plan.id} plan={plan} onEdit={onEdit} onRemove={onRemove} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
