import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { ErrorEventSummary } from "../domain/contract";
import { formatDateTime, formatRelative } from "../domain/format";

export function RecentEvents({ events }: { events: ErrorEventSummary[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Последние события</CardTitle>
        <CardDescription>Не больше 10, новые сверху</CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <Table className="**:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4">
          <TableHeader>
            <TableRow>
              <TableHead className="font-normal">Когда</TableHead>
              <TableHead className="font-normal">Версия</TableHead>
              <TableHead className="font-normal">ОС</TableHead>
              <TableHead className="font-normal">Устройство</TableHead>
              <TableHead className="font-normal">Пользователь</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((event) => (
              <TableRow key={event.id}>
                <TableCell>
                  <time dateTime={event.received_at} title={formatDateTime(event.received_at)}>
                    {formatRelative(event.received_at)}
                  </time>
                </TableCell>
                <TableCell className="font-mono text-xs">{event.app_version}</TableCell>
                <TableCell>{event.os_version}</TableCell>
                <TableCell>{event.device}</TableCell>
                <TableCell className="font-mono text-xs">
                  {event.user_id ?? <span className="font-sans text-muted-foreground">—</span>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
