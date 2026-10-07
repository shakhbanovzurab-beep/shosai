"use client";
import type { ColumnDef } from "@tanstack/react-table";
import { Subscribe } from "@tanstack/react-table";
import { MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DataTableFeatures } from "@/lib/data-table-features";

import { formatJoinedDate, parseJoinedDate } from "../domain/joined-date";
import type { UserRow } from "../domain/user";
import { teamLabels } from "../domain/user-labels";
import { AvatarCell, RoleCell, StatusBadge, WorkspaceCell } from "./users-cells";

export const usersColumns: ColumnDef<DataTableFeatures, UserRow>[] = [
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
              aria-label="Выбрать всех пользователей"
              checked={checked}
              onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
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
              aria-label={`Выбрать ${row.original.name}`}
              checked={checked}
              onCheckedChange={(value) => row.toggleSelected(!!value)}
            />
          )}
        </Subscribe>
      </div>
    ),
    enableHiding: false,
    enableSorting: false,
  },
  {
    accessorKey: "name",
    header: "Пользователь",
    cell: ({ row }) => (
      <div className="flex items-center gap-3">
        <AvatarCell name={row.original.name} lastActive={row.original.lastActive} />
        <div className="min-w-0">
          <div className="truncate font-medium text-foreground text-sm">{row.original.name}</div>
          <div className="truncate text-muted-foreground text-sm">{row.original.email}</div>
        </div>
      </div>
    ),
  },
  {
    accessorKey: "role",
    header: "Роль / команда",
    filterFn: "equalsString",
    cell: ({ row }) => <RoleCell role={row.original.role} team={row.original.team} />,
  },
  {
    accessorKey: "team",
    header: "Команда",
    filterFn: "equalsString",
    cell: ({ row }) => <div className="text-sm">{teamLabels[row.original.team]}</div>,
  },
  {
    accessorKey: "workspace",
    header: "Пространство",
    filterFn: "arrIncludes",
    cell: ({ row }) => <WorkspaceCell workspaces={row.original.workspace} />,
  },
  {
    accessorKey: "status",
    header: "Статус",
    filterFn: "equalsString",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    id: "joinedDate",
    accessorFn: (row) => parseJoinedDate(row.joinedDate).getTime(),
    header: "Дата регистрации",
    cell: ({ row }) => (
      <div className="whitespace-nowrap text-foreground text-sm">{formatJoinedDate(row.original.joinedDate)}</div>
    ),
  },
  {
    id: "actions",
    header: () => <div className="text-right">Действия</div>,
    cell: ({ row }) => (
      <div className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              aria-label={`Действия для ${row.original.name}`}
              className="size-8 rounded-md text-muted-foreground hover:bg-muted/50"
              size="icon-sm"
              variant="ghost"
            >
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem>Открыть профиль</DropdownMenuItem>
            <DropdownMenuItem>Изменить пользователя</DropdownMenuItem>
            <DropdownMenuItem>Управлять командой</DropdownMenuItem>
            <DropdownMenuItem>Отправить приглашение повторно</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive">Деактивировать пользователя</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    ),
    enableHiding: false,
    enableSorting: false,
  },
];
