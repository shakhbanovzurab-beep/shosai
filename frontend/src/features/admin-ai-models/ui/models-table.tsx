"use client";

import { useState } from "react";

import { Star } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { AiModel } from "../domain/contract";
import { formatCompact, formatInteger, formatPrice, formatUsd } from "../domain/format";
import { COLUMNS, compare, type Sort, type SortKey } from "../domain/models-sort";
import { patchModel } from "../model/ai-models-store";
import { SortHeader } from "./models-table-header";

export function ModelsTable({ models }: { models: AiModel[] }) {
  const [sort, setSort] = useState<Sort>({ key: "month_spend", desc: true });
  const rows = models.toSorted((a, b) => compare(a, b, sort));
  const enabled = models.filter((model) => model.enabled);
  const defaultModel = models.find((model) => model.is_default);

  function onSort(key: SortKey) {
    setSort((current) =>
      current.key === key ? { key, desc: !current.desc } : { key, desc: key !== "name" && key !== "provider" },
    );
  }

  return (
    <Card>
      <CardHeader className="border-b has-data-[slot=card-action]:grid-cols-1 md:has-data-[slot=card-action]:grid-cols-[1fr_auto]">
        <CardTitle className="font-normal">Модели</CardTitle>
        <CardDescription>
          Включённые модели доступны пользователям Leo. Цены — в долларах за 1 млн токенов. Включено {enabled.length} из{" "}
          {models.length}.
        </CardDescription>
        <CardAction className="col-start-1 row-start-auto flex w-full flex-col gap-1.5 justify-self-stretch md:col-start-2 md:row-span-2 md:row-start-1 md:w-64 md:justify-self-end">
          <span id="ai-default-model-label" className="text-muted-foreground text-xs">
            Модель Leo по умолчанию
          </span>
          <Select
            value={defaultModel?.id ?? ""}
            onValueChange={(id) => void patchModel(id, { is_default: true })}
            disabled={enabled.length === 0}
          >
            <SelectTrigger size="sm" className="w-full" aria-labelledby="ai-default-model-label">
              <SelectValue placeholder="Не выбрана" />
            </SelectTrigger>
            <SelectContent position="popper" align="end">
              <SelectGroup>
                {enabled.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
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
                  Нет моделей.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((model) => (
                <TableRow key={model.id} data-disabled={model.enabled ? undefined : ""} className="group">
                  <TableCell className="max-w-72 py-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate font-medium group-data-disabled:text-muted-foreground">
                        {model.name}
                      </span>
                      {model.is_default ? (
                        <Badge variant="secondary">
                          <Star aria-hidden="true" />
                          По умолчанию
                        </Badge>
                      ) : null}
                    </div>
                    <div className="truncate font-mono text-muted-foreground text-xs">{model.openrouter_id}</div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{model.provider}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCompact(model.context_length)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatPrice(model.price_input_per_m)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatPrice(model.price_output_per_m)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatUsd(model.month_spend)}</TableCell>
                  <TableCell className="text-right text-muted-foreground tabular-nums">
                    {formatInteger(model.month_requests)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Switch
                      checked={model.enabled}
                      disabled={model.is_default}
                      onCheckedChange={(checked) => void patchModel(model.id, { enabled: checked })}
                      aria-label={`Модель ${model.name} доступна пользователям`}
                      title={model.is_default ? "Модель по умолчанию нельзя выключить" : undefined}
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>

      <CardFooter className="text-muted-foreground text-xs">
        Модель по умолчанию нельзя выключить — сначала назначьте другую.
      </CardFooter>
    </Card>
  );
}
