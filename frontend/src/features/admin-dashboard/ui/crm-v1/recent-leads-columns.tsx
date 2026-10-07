"use client";
import type { ColumnDef } from "@tanstack/react-table";
import { Subscribe } from "@tanstack/react-table";
import { EllipsisVertical } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DataTableFeatures } from "@/lib/data-table-features";

import type { RecentLeadRow } from "../../domain/crm-v1/recent-lead";
import { leadSourceLabels, leadStatusLabels, recentLeadColumnLabels } from "../../domain/crm-v1/recent-lead-labels";

export const recentLeadsColumns: ColumnDef<DataTableFeatures, RecentLeadRow>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <div className="flex items-center justify-center">
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
              aria-label="Выбрать все"
            />
          )}
        </Subscribe>
      </div>
    ),
    cell: ({ row }) => (
      <div className="flex items-center justify-center">
        <Subscribe source={row.table.atoms.rowSelection} selector={(selection) => Boolean(selection?.[row.id])}>
          {(checked) => (
            <Checkbox
              checked={checked}
              onCheckedChange={(value) => row.toggleSelected(!!value)}
              aria-label="Выбрать строку"
            />
          )}
        </Subscribe>
      </div>
    ),
    enableHiding: false,
  },
  {
    accessorKey: "id",
    header: recentLeadColumnLabels.id,
    cell: ({ row }) => <span className="tabular-nums">{row.original.id}</span>,
    enableHiding: false,
  },
  {
    accessorKey: "name",
    header: recentLeadColumnLabels.name,
    cell: ({ row }) => row.original.name,
    enableHiding: false,
  },
  {
    accessorKey: "company",
    header: recentLeadColumnLabels.company,
    cell: ({ row }) => row.original.company,
  },
  {
    accessorKey: "status",
    header: recentLeadColumnLabels.status,
    cell: ({ row }) => (
      <Badge variant="secondary">{leadStatusLabels[row.original.status] ?? row.original.status}</Badge>
    ),
  },
  {
    accessorKey: "source",
    header: recentLeadColumnLabels.source,
    cell: ({ row }) => <Badge variant="outline">{leadSourceLabels[row.original.source] ?? row.original.source}</Badge>,
  },
  {
    accessorKey: "lastActivity",
    header: recentLeadColumnLabels.lastActivity,
    cell: ({ row }) => <span className="text-muted-foreground tabular-nums">{row.original.lastActivity}</span>,
  },
  {
    id: "actions",
    cell: () => (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="flex size-8 text-muted-foreground">
            <EllipsisVertical />
            <span className="sr-only">Открыть меню</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-36">
          <DropdownMenuGroup>
            <DropdownMenuItem>Открыть</DropdownMenuItem>
            <DropdownMenuItem>Назначить</DropdownMenuItem>
            <DropdownMenuItem>В архив</DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem variant="destructive">Удалить</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
    enableHiding: false,
  },
];
