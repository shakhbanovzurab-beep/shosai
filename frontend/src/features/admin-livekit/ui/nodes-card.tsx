import { cn } from "cn";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { LiveKitNode } from "../domain/contract";
import { formatInteger, formatPercent, NO_DATA } from "../domain/format";
import { NodeStateBadge } from "./status-badge";

/** Load bar: amber from 70 %, red from 85 %; the number beside it carries the value; null is "no data". */
function LoadMeter({ value, label }: { value: number | null; label: string }) {
  if (value === null)
    return (
      <span className="text-muted-foreground text-xs">
        <span aria-hidden="true">{NO_DATA}</span>
        <span className="sr-only">{`${label}: нет данных`}</span>
      </span>
    );
  let tone = "";
  if (value >= 85) tone = "*:data-[slot=progress-indicator]:bg-red-500";
  else if (value >= 70) tone = "*:data-[slot=progress-indicator]:bg-amber-500";
  return (
    <div className="flex min-w-32 items-center gap-2">
      <Progress value={value} aria-label={label} className={cn("h-1.5 flex-1", tone)} />
      <span className="w-12 text-right text-xs tabular-nums">{formatPercent(value)}</span>
    </div>
  );
}

export function NodesCard({ nodes }: { nodes: LiveKitNode[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Узлы</CardTitle>
        <CardDescription>Нагрузка на узлы LiveKit по данным Prometheus.</CardDescription>
      </CardHeader>
      <CardContent>
        {nodes.length === 0 ? (
          <p className="py-6 text-center text-muted-foreground text-sm">
            Нет данных: Prometheus не ответил или ещё не опрашивает LiveKit.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Узел</TableHead>
                <TableHead>ЦП</TableHead>
                <TableHead>Память</TableHead>
                <TableHead className="text-right">Комнаты</TableHead>
                <TableHead className="text-right">Участники</TableHead>
                <TableHead>Статус</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nodes.map((node) => (
                <TableRow key={node.id}>
                  <TableCell className="font-mono text-xs">{node.id}</TableCell>
                  <TableCell>
                    <LoadMeter value={node.cpu_percent} label={`Загрузка ЦП узла ${node.id}`} />
                  </TableCell>
                  <TableCell>
                    <LoadMeter value={node.memory_percent} label={`Память узла ${node.id}`} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatInteger(node.rooms)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatInteger(node.participants)}</TableCell>
                  <TableCell>
                    <NodeStateBadge state={node.state} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
