"use client";
import type { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DataTableFeatures } from "@/lib/data-table-features";

import type { Role } from "../../domain/role";
import { formatLastReview, roleOwnerLabels, roleStatusLabels } from "../../domain/role-labels";

export const rolesColumns: ColumnDef<DataTableFeatures, Role>[] = [
  {
    id: "group",
    accessorKey: "group",
    filterFn: "equalsString",
    enableHiding: true,
  },
  {
    id: "role",
    accessorKey: "role",
    header: "Роль",
    size: 180,
    minSize: 180,
    cell: ({ row }) => <span className="font-medium text-sm">{row.original.role}</span>,
  },
  {
    id: "accessLevel",
    accessorKey: "accessLevel",
    header: "Уровень доступа",
    size: 150,
    cell: ({ row }) => (
      <Badge className="rounded-sm" variant="outline">
        {row.original.accessLevel}
      </Badge>
    ),
  },
  {
    id: "users",
    accessorKey: "users",
    header: "Пользователи",
    size: 120,
    cell: ({ row }) => <span className="text-sm">{row.original.users}</span>,
  },
  {
    id: "permissionSets",
    accessorFn: (row) => row.permissionSets.join(" "),
    header: "Наборы прав",
    size: 310,
    cell: ({ row }) => (
      <div className="flex flex-wrap items-center justify-start gap-2">
        {row.original.permissionSets.slice(0, 3).map((set) => (
          <Badge className="rounded-sm" variant="outline" key={set}>
            {set}
          </Badge>
        ))}
        {row.original.permissionSets.length > 3 ? (
          <span className="text-sm tabular-nums">+{row.original.permissionSets.length - 3}</span>
        ) : null}
      </div>
    ),
  },
  {
    id: "lastReview",
    accessorKey: "lastReview",
    header: "Последняя проверка",
    size: 160,
    cell: ({ row }) => <span className="text-sm">{formatLastReview(row.original.lastReview)}</span>,
  },
  {
    id: "owner",
    accessorKey: "owner",
    header: "Владелец",
    size: 110,
    filterFn: "equalsString",
    cell: ({ row }) => <span className="text-sm">{roleOwnerLabels[row.original.owner] ?? row.original.owner}</span>,
  },
  {
    id: "status",
    accessorKey: "status",
    header: "Статус",
    size: 160,
    filterFn: "equalsString",
    cell: ({ row }) => (
      <Badge className="rounded-sm" variant="outline">
        {roleStatusLabels[row.original.status]}
      </Badge>
    ),
  },
  {
    id: "actions",
    header: "",
    size: 70,
    cell: ({ row }) => {
      const isSystemRole = row.original.group === "System roles";
      const needsReview = row.original.status === "Needs review";

      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="Действия с ролью">
              <MoreVertical />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end">
            <DropdownMenuGroup>
              {needsReview ? <DropdownMenuItem>Проверить изменения</DropdownMenuItem> : null}
              <DropdownMenuItem>Подробнее</DropdownMenuItem>
              <DropdownMenuItem disabled={isSystemRole}>Изменить роль</DropdownMenuItem>
              <DropdownMenuItem disabled={isSystemRole}>Дублировать роль</DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem>Проверить права</DropdownMenuItem>
              <DropdownMenuItem>Управлять участниками</DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem disabled={isSystemRole} variant="destructive">
                Архивировать роль
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      );
    },
    enableColumnFilter: false,
  },
];
