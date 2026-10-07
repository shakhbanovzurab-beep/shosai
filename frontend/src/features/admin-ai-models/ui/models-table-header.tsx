"use client";

import type { ReactNode } from "react";

import { cn } from "cn";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { TableHead } from "@/components/ui/table";

import type { COLUMNS, Sort, SortKey } from "../domain/models-sort";

/* A sortable column header with its sort state for assistive tech. */

export function SortHeader({
  column,
  sort,
  onSort,
}: {
  column: (typeof COLUMNS)[number];
  sort: Sort;
  onSort: (key: SortKey) => void;
}) {
  const active = sort.key === column.key;
  let icon: ReactNode = <ArrowUpDown className="size-3.5 opacity-50" aria-hidden="true" />;
  if (active)
    icon = sort.desc ? (
      <ArrowDown className="size-3.5" aria-hidden="true" />
    ) : (
      <ArrowUp className="size-3.5" aria-hidden="true" />
    );
  let ariaSort: "ascending" | "descending" | "none" = "none";
  if (active) ariaSort = sort.desc ? "descending" : "ascending";

  return (
    <TableHead aria-sort={ariaSort} className={cn("h-10 font-normal", column.numeric && "text-right")}>
      <button
        type="button"
        onClick={() => onSort(column.key)}
        className={cn(
          "-mx-1 inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
          active && "text-foreground",
          column.numeric && "flex-row-reverse",
        )}
      >
        {column.label}
        {icon}
      </button>
    </TableHead>
  );
}
