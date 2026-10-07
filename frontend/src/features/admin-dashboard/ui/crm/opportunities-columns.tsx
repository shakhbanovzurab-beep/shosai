"use client";
import type { ColumnDef } from "@tanstack/react-table";
import { Subscribe } from "@tanstack/react-table";
import { cn } from "cn";
import { Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { DataTableFeatures } from "@/lib/data-table-features";

import type { OpportunityRow } from "../../domain/crm/opportunity";
import { formatUsdValue, healthLabels, stageLabels } from "../../domain/crm/opportunity-labels";

const healthStripSlots = Array.from({ length: 18 }, (_, index) => ({
  id: `strip-${index + 1}`,
  threshold: index + 1,
}));

function getHealthScore(health: OpportunityRow["health"]) {
  switch (health) {
    case "On Track":
      return 18;
    case "Needs Review":
      return 11;
    case "At Risk":
      return 7;
    case "On Hold":
      return 4;
    default:
      return 0;
  }
}

export const opportunitiesColumns: ColumnDef<DataTableFeatures, OpportunityRow>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Subscribe
        source={table.atoms.rowSelection}
        selector={() =>
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && !table.getIsAllPageRowsSelected() && "indeterminate")
        }
      >
        {(checked) => (
          <Checkbox
            checked={checked}
            onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
            aria-label="Выбрать все сделки"
          />
        )}
      </Subscribe>
    ),
    cell: ({ row }) => (
      <Subscribe source={row.table.atoms.rowSelection} selector={(selection) => Boolean(selection?.[row.id])}>
        {(checked) => (
          <Checkbox
            checked={checked}
            onCheckedChange={(value) => row.toggleSelected(!!value)}
            aria-label={`Выбрать ${row.original.account}`}
          />
        )}
      </Subscribe>
    ),
    enableHiding: false,
  },
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => <div className="text-sm tracking-tight">{row.original.id}</div>,
    enableHiding: false,
  },
  {
    accessorKey: "account",
    header: "Клиент",
    cell: ({ row }) => <div className="font-medium text-sm">{row.original.account}</div>,
  },
  {
    accessorKey: "stage",
    header: "Этап",
    cell: ({ row }) => (
      <Badge variant="outline" className="rounded-full px-2.5">
        {stageLabels[row.original.stage] ?? row.original.stage}
      </Badge>
    ),
    filterFn: "equalsString",
  },
  {
    accessorKey: "priority",
    header: "Приоритет",
    cell: ({ row }) => <div className="text-sm">{row.original.priority}</div>,
  },
  {
    accessorKey: "health",
    header: "Состояние",
    cell: ({ row }) => (
      <div className="flex items-end gap-0.5" title={healthLabels[row.original.health] ?? row.original.health}>
        <span className="sr-only">{healthLabels[row.original.health] ?? row.original.health}</span>
        {healthStripSlots.map((slot) => (
          <div
            key={`${row.original.id}-${slot.id}`}
            className={cn(
              "h-5 w-1 rounded-full",
              slot.threshold <= getHealthScore(row.original.health) ? "bg-green-500/85" : "bg-green-500/15",
            )}
          />
        ))}
      </div>
    ),
    filterFn: "equalsString",
  },
  {
    accessorKey: "value",
    header: "Сумма",
    cell: ({ row }) => <div className="font-medium text-sm tabular-nums">{formatUsdValue(row.original.value)}</div>,
  },
  {
    id: "actions",
    header: () => <div className="text-right">Изменить</div>,
    cell: () => (
      <div className="text-right">
        <Button
          variant="ghost"
          size="icon"
          className="size-8 rounded-full text-muted-foreground hover:bg-transparent focus-visible:bg-transparent"
        >
          <Pencil />
          <span className="sr-only">Изменить сделку</span>
        </Button>
      </div>
    ),
    enableHiding: false,
  },
];
