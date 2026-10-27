"use client";

import { useState } from "react";

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { AiModel, RoleDefault } from "../domain/contract";
import { COLUMNS, compare, type Sort, type SortKey } from "../domain/models-sort";
import { heldByDefaults } from "../domain/roles";
import { AddModelDialog } from "./add-model-dialog";
import { SortHeader } from "./models-table-header";
import { ModelRow } from "./models-table-row";

export function ModelsTable({ models, defaults }: { models: AiModel[]; defaults: RoleDefault[] }) {
  const [sort, setSort] = useState<Sort>({ key: "month_spend", desc: true });
  const rows = models.toSorted((a, b) => compare(a, b, sort));
  const enabled = models.filter((model) => model.enabled);

  function onSort(key: SortKey) {
    setSort((current) =>
      current.key === key ? { key, desc: !current.desc } : { key, desc: key !== "name" && key !== "provider" },
    );
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="font-normal">Модели</CardTitle>
        <CardDescription>
          Включённые модели доступны пользователям Leo и Studio. Цены — в долларах за 1 млн токенов. Включено{" "}
          {enabled.length} из {models.length}.
        </CardDescription>
        <CardAction>
          <AddModelDialog />
        </CardAction>
      </CardHeader>

      <CardContent className="px-0">
        <Table className="[&_td:first-child]:pl-4 [&_td:last-child]:pr-4 [&_th:first-child]:pl-4 [&_th:last-child]:pr-4">
          <TableHeader className="[&_tr]:border-border/50">
            <TableRow className="hover:bg-transparent">
              {COLUMNS.map((column) => (
                <SortHeader key={column.key} column={column} sort={sort} onSort={onSort} />
              ))}
              <TableHead className="h-10 text-right font-normal text-muted-foreground">Включена</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="[&_tr]:border-border/50">
            {rows.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={COLUMNS.length + 1} className="h-24 text-center text-muted-foreground">
                  В каталоге пока нет моделей. Добавьте первую по её id в OpenRouter.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((model) => <ModelRow key={model.id} model={model} held={heldByDefaults(defaults, model.id)} />)
            )}
          </TableBody>
        </Table>
      </CardContent>

      <CardFooter className="text-muted-foreground text-xs">
        Модель, которая держит умолчание роли, нельзя выключить — сначала назначьте роли другую. Выключенную модель
        можно убрать из каталога; расходы по ней остаются в отчётах.
      </CardFooter>
    </Card>
  );
}
