"use client";
import { useState } from "react";

import { type ColumnFiltersState, type PaginationState, useTable } from "@tanstack/react-table";
import { AlertTriangle, ChevronRight, FileUp } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { dataTableFeatures } from "@/lib/data-table-features";

import { getRoleGroupFilterValue, getRoleTypeFilter, type Role } from "../domain/role";
import { rolesColumns } from "./roles-table/columns";
import { RolesTable } from "./roles-table/table";

export function Roles({ roles }: { roles: Role[] }) {
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 12,
  });

  const table = useTable({
    features: dataTableFeatures,
    data: roles,
    columns: rolesColumns,
    defaultColumn: {
      size: 140,
      minSize: 80,
      maxSize: 420,
    },
    state: { columnFilters, pagination },
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
    autoResetPageIndex: false,
    initialState: {
      columnVisibility: { group: false },
    },
  });

  const groupFilter = (table.getColumn("group")?.getFilterValue() as string | undefined) ?? "";
  const typeFilter = getRoleTypeFilter(groupFilter);
  const ownerFilter = (table.getColumn("owner")?.getFilterValue() as string | undefined) ?? "All";
  const statusFilter = (table.getColumn("status")?.getFilterValue() as string | undefined) ?? "All";

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl tracking-tight">Роли</h1>
          <p className="text-muted-foreground text-sm">Управляйте ролями доступа и правами в организации.</p>
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline">
            <FileUp data-icon="inline-start" />
            Импорт JSON
          </Button>
          <Button size="sm">Создать роль</Button>
        </div>
      </div>

      <Tabs className="h-full gap-4" defaultValue="roles">
        <TabsList
          variant="line"
          className="w-full justify-start gap-2 border-b ps-0 *:data-[slot=tabs-trigger]:flex-none"
        >
          <TabsTrigger value="roles">Роли</TabsTrigger>
          <TabsTrigger value="permission-sets">Наборы прав</TabsTrigger>
          <TabsTrigger value="access-reviews">Проверки доступа</TabsTrigger>
        </TabsList>

        <TabsContent value="roles">
          <div className="flex flex-col gap-4">
            <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-50">
              <AlertTriangle className="size-4" />
              <AlertTitle>Требуется проверка</AlertTitle>
              <AlertDescription>В 3 ролях есть непроверенные изменения прав.</AlertDescription>
              <AlertAction>
                <Button size="sm" variant="link">
                  Проверить изменения
                  <ChevronRight data-icon="inline-end" />
                </Button>
              </AlertAction>
            </Alert>

            <div className="overflow-hidden rounded-xl border border-border/70 bg-background">
              <div className="flex flex-col items-stretch gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
                <div className="flex flex-wrap items-center gap-2">
                  <Select
                    value={typeFilter}
                    onValueChange={(v) => {
                      table.getColumn("group")?.setFilterValue(getRoleGroupFilterValue(v));
                      table.setPageIndex(0);
                    }}
                  >
                    <SelectTrigger size="sm">
                      <span className="text-muted-foreground">Тип:</span>
                      <SelectValue placeholder="Все" />
                    </SelectTrigger>
                    <SelectContent position="popper" align="start">
                      <SelectGroup>
                        <SelectItem value="All">Все</SelectItem>
                        <SelectItem value="System">Системные</SelectItem>
                        <SelectItem value="Custom">Пользовательские</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>

                  <Select
                    value={ownerFilter}
                    onValueChange={(v) => {
                      table.getColumn("owner")?.setFilterValue(v === "All" ? undefined : v);
                      table.setPageIndex(0);
                    }}
                  >
                    <SelectTrigger size="sm">
                      <span className="text-muted-foreground">Владелец:</span>
                      <SelectValue placeholder="Все" />
                    </SelectTrigger>
                    <SelectContent position="popper" align="start">
                      <SelectGroup>
                        <SelectItem value="All">Все</SelectItem>
                        <SelectItem value="System">Система</SelectItem>
                        <SelectItem value="Jane Doe">Jane Doe</SelectItem>
                        <SelectItem value="Alex Kim">Alex Kim</SelectItem>
                        <SelectItem value="Chris Lee">Chris Lee</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>

                  <Select
                    value={statusFilter}
                    onValueChange={(v) => {
                      table.getColumn("status")?.setFilterValue(v === "All" ? undefined : v);
                      table.setPageIndex(0);
                    }}
                  >
                    <SelectTrigger size="sm">
                      <span className="text-muted-foreground">Статус:</span>
                      <SelectValue placeholder="Все" />
                    </SelectTrigger>
                    <SelectContent position="popper" align="start">
                      <SelectGroup>
                        <SelectItem value="All">Все</SelectItem>
                        <SelectItem value="Active">Активна</SelectItem>
                        <SelectItem value="Needs review">Требует проверки</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <RolesTable table={table} />
            </div>
          </div>
        </TabsContent>
        <TabsContent value="permission-sets">
          <div className="flex h-full items-center justify-center rounded-md border border-dashed text-muted-foreground text-sm">
            Раздел «Наборы прав» скоро появится
          </div>
        </TabsContent>
        <TabsContent value="access-reviews">
          <div className="flex h-full items-center justify-center rounded-md border border-dashed text-muted-foreground text-sm">
            Раздел «Проверки доступа» скоро появится
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
