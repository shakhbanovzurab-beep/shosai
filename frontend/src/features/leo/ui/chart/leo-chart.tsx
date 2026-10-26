"use client";

import * as React from "react";

import { ChartColumn, Table2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import type { ChartArtifact } from "../../domain/artifacts";
import { ChartPlot } from "./chart-plot";
import { ChartTable } from "./chart-table";

/*
 * График в ответе Leo оператору (agent шаг 16, AG-D10): строки посчитал инструмент платформы, кабинет только рисует.
 * У каждого графика есть таблица с теми же строками. Админ-панель только на русском (docs/i18n.md).
 */

export function LeoChart({ chart }: { readonly chart: ChartArtifact }) {
  const [asTable, setAsTable] = React.useState(false);
  return (
    <figure className="flex flex-col gap-2 rounded-lg border p-3">
      <figcaption className="flex items-center justify-between gap-2">
        <span className="font-medium text-sm">{chart.alt}</span>
        <Button
          variant="ghost"
          size="icon-sm"
          className="shrink-0 text-muted-foreground"
          aria-label={asTable ? "Показать графиком" : "Показать таблицей"}
          title={asTable ? "Показать графиком" : "Показать таблицей"}
          onClick={() => setAsTable((value) => !value)}
        >
          {asTable ? <ChartColumn /> : <Table2 />}
        </Button>
      </figcaption>
      {asTable ? (
        <ChartTable spec={chart.spec} caption={chart.alt} />
      ) : (
        <ChartPlot spec={chart.spec} label={chart.alt} />
      )}
    </figure>
  );
}
