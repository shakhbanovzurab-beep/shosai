import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { LiveKitEgress } from "../domain/contract";
import { formatBytes, formatDateTime, NO_DATA } from "../domain/format";
import { EgressBadge } from "./status-badge";

export function EgressCard({ egress }: { egress: LiveKitEgress[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Записи и экспорт</CardTitle>
        <CardDescription>Последние задания egress: записи встреч и трансляции.</CardDescription>
      </CardHeader>
      <CardContent>
        {egress.length === 0 ? (
          <p className="py-6 text-center text-muted-foreground text-sm">Записей пока не было.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Комната</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Начало</TableHead>
                <TableHead className="text-right">Размер файла</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {egress.map((job) => (
                <TableRow key={job.id}>
                  <TableCell className="max-w-64 truncate font-mono text-xs">{job.room_name}</TableCell>
                  <TableCell>
                    <EgressBadge status={job.status} />
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {job.started_at === null ? NO_DATA : formatDateTime(job.started_at)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {job.file_size_bytes === null ? (
                      <>
                        <span aria-hidden="true" className="text-muted-foreground">
                          —
                        </span>
                        <span className="sr-only">Файла пока нет</span>
                      </>
                    ) : (
                      formatBytes(job.file_size_bytes)
                    )}
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
