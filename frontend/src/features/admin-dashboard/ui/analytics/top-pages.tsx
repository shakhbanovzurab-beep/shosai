import { Ellipsis } from "lucide-react";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { topPages } from "../../data/analytics/top-pages";

export function TopPages() {
  return (
    <Card className="h-full gap-2">
      <CardHeader>
        <CardTitle className="font-normal">Эффективность страниц</CardTitle>
        <CardAction>
          <Ellipsis className="size-4" />
        </CardAction>
      </CardHeader>

      <CardContent className="px-0">
        <Table className="[&_td:first-child]:pl-4 [&_td:last-child]:pr-4 [&_th:first-child]:pl-4 [&_th:last-child]:pr-4">
          <TableHeader className="[&_tr]:border-border/50">
            <TableRow className="hover:bg-transparent">
              <TableHead className="h-8" />
              <TableHead className="h-8 w-24 text-right font-normal">Просмотры</TableHead>
              <TableHead className="h-8 w-24 text-right font-normal">Ср. время</TableHead>
              <TableHead className="h-8 w-20 text-right font-normal">Отказы</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="[&_tr]:border-border/50">
            {topPages.map((page) => (
              <TableRow className="hover:bg-transparent" key={page.path}>
                <TableCell className="max-w-0 truncate py-4 font-medium">{page.path}</TableCell>
                <TableCell className="text-right tabular-nums">{page.views}</TableCell>
                <TableCell className="text-right text-muted-foreground tabular-nums">{page.time}</TableCell>
                <TableCell className="text-right text-muted-foreground tabular-nums">{page.bounce}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
