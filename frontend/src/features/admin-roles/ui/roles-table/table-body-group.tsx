import { FlexRender } from "@tanstack/react-table";
import { cn } from "cn";

import { Badge } from "@/components/ui/badge";
import { TableCell, TableRow } from "@/components/ui/table";

import { roleGroupLabels } from "../../domain/role-labels";
import type { RoleTableRow } from "./table";

export function TableBodyGroup({
  group,
  totalCount,
  colCount,
}: {
  group: { label: string; rows: RoleTableRow[] };
  totalCount: number;
  colCount: number;
}) {
  return (
    <>
      <TableRow className="h-10 bg-muted">
        <TableCell className="px-4 text-foreground/60 text-sm" colSpan={colCount}>
          {roleGroupLabels[group.label] ?? group.label}{" "}
          <Badge variant="outline" className="ml-2 rounded-sm bg-transparent text-muted-foreground text-xs">
            {group.rows.length} из {totalCount}
          </Badge>
        </TableCell>
      </TableRow>
      {group.rows.map((row) => (
        <TableRow key={row.id} className="h-12 hover:bg-muted/20">
          {row.getVisibleCells().map((cell, index) => (
            <TableCell
              key={cell.id}
              style={{ width: cell.column.getSize() }}
              className={cn(
                "border-r px-4 align-middle",
                index === row.getVisibleCells().length - 1 && "border-r-0",
                index === 0 ? "text-left" : "text-center",
              )}
            >
              <FlexRender cell={cell} />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}
