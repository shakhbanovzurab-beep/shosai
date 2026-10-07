"use client";
import * as React from "react";

import {
  type ColumnFiltersState,
  type ColumnVisibilityState,
  type PaginationState,
  useTable,
} from "@tanstack/react-table";
import { ChevronDownIcon, ListFilter } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dataTableFeatures } from "@/lib/data-table-features";

import { opportunities } from "../../data/crm/opportunities";
import { healthOptions, stageOptions } from "../../domain/crm/opportunity";
import { healthLabels, stageLabels } from "../../domain/crm/opportunity-labels";
import { opportunitiesColumns } from "./opportunities-columns";
import { OpportunitiesPagination } from "./opportunities-pagination";

const opportunityCountFormatter = new Intl.NumberFormat("ru-RU");

export function OpportunitiesSection() {
  const [rowSelection, setRowSelection] = React.useState({});
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [columnVisibility] = React.useState<ColumnVisibilityState>({});
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  });

  const table = useTable({
    features: dataTableFeatures,
    data: opportunities,
    columns: opportunitiesColumns,
    state: {
      rowSelection,
      columnFilters,
      columnVisibility,
      pagination,
    },
    getRowId: (row) => row.id,
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
  });
  const stageFilter = (table.getColumn("stage")?.getFilterValue() as string | undefined) ?? "all";
  const healthFilter = (table.getColumn("health")?.getFilterValue() as string | undefined) ?? "all";
  const filteredOpportunityCount = table.getFilteredRowModel().rows.length;
  const visibleOpportunityCount = table.getRowModel().rows.length;

  return (
    <section>
      <Card>
        <CardHeader>
          <CardTitle className="leading-none">Последние сделки</CardTitle>
          <CardDescription>
            Отслеживайте квалифицированных лидов на этапах выявления потребностей, коммерческого предложения и закрытия.
          </CardDescription>
          <CardAction>
            <div className="flex items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    <ListFilter data-icon="inline-start" />
                    Этап
                    <ChevronDownIcon data-icon="inline-end" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuRadioGroup
                    value={stageFilter}
                    onValueChange={(value) => {
                      table.getColumn("stage")?.setFilterValue(value === "all" ? undefined : value);
                      table.setPageIndex(0);
                    }}
                  >
                    {stageOptions.map((option) => (
                      <DropdownMenuRadioItem key={option} value={option}>
                        {option === "all" ? "Все этапы" : stageLabels[option]}
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    <ListFilter data-icon="inline-start" />
                    Состояние
                    <ChevronDownIcon data-icon="inline-end" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuRadioGroup
                    value={healthFilter}
                    onValueChange={(value) => {
                      table.getColumn("health")?.setFilterValue(value === "all" ? undefined : value);
                      table.setPageIndex(0);
                    }}
                  >
                    {healthOptions.map((option) => (
                      <DropdownMenuRadioItem key={option} value={option}>
                        {option === "all" ? "Любое состояние" : healthLabels[option]}
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 px-0">
          <div className="overflow-hidden">
            <Table className="**:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4 **:data-[slot='table-cell']:py-4">
              <TableHeader className="border-t **:data-[slot='table-head']:h-11 **:data-[slot='table-head']:font-medium **:data-[slot='table-head']:text-foreground **:data-[slot='table-head']:text-sm">
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id} colSpan={header.colSpan}>
                        {header.isPlaceholder ? null : <table.FlexRender header={header} />}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody className="**:data-[slot='table-row']:border-border/50 **:data-[slot='table-row']:hover:bg-transparent">
                {table.getRowModel().rows.length ? (
                  table.getRowModel().rows.map((row) => (
                    <TableRow key={row.id} data-state={table.state.rowSelection[row.id] && "selected"}>
                      {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id}>
                          <table.FlexRender cell={cell} />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={table.getVisibleLeafColumns().length} className="h-24 text-center">
                      Ничего не найдено.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <div className="flex items-center justify-between gap-4 px-4 pb-1">
            <p className="text-muted-foreground text-sm">
              Показано {visibleOpportunityCount} из {opportunityCountFormatter.format(filteredOpportunityCount)} сделок
            </p>

            <OpportunitiesPagination table={table} />
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
