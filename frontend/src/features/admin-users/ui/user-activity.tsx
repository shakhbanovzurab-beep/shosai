import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deviceName } from "@/features/identity/domain/device-name";

import type { AdminUserCard } from "../domain/contract";
import { formatDateTime, formatUsd } from "../domain/format";
import { clientLabel, outcomeLabel } from "../domain/labels";
import { useDisplayZone } from "./use-display-zone";

type UserCard = AdminUserCard;

/** Расходы на ИИ за сегодня, неделю и месяц делового пояса платформы (ADR 0058), в обоих домах. */
export function SpendCard({ spend }: { spend: UserCard["spend"] }) {
  const { label } = useDisplayZone();
  const rows = [
    ["Сегодня", spend.today_usd],
    ["Неделя", spend.week_usd],
    ["Месяц", spend.month_usd],
  ] as const;
  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle>Расходы на ИИ</CardTitle>
        <CardDescription>Себестоимость вызовов моделей, сутки и месяцы по {label}.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col gap-2">
          {rows.map(([label, amount]) => (
            <div key={label} className="flex items-baseline justify-between gap-4">
              <dt className="text-muted-foreground text-sm">{label}</dt>
              <dd className="font-medium tabular-nums">{formatUsd(amount)}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/** Карточка с таблицей журнала; без строк — только строка о том, что их нет. */
function ActivityCard({
  title,
  description,
  columns,
  rows,
}: {
  title: string;
  description: string;
  columns: readonly string[];
  rows: ReactNode[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      {rows.length ? (
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                {columns.map((column) => (
                  <TableHead key={column} className="first:ps-6 last:pe-6">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>{rows}</TableBody>
          </Table>
        </CardContent>
      ) : null}
    </Card>
  );
}

/** Открытые сессии: устройство, адрес и когда им пользовались. */
export function SessionsCard({ sessions }: { sessions: UserCard["sessions"] }) {
  const shown = useDisplayZone();
  return (
    <ActivityCard
      title="Сессии"
      description={sessions.length ? "Открытые сейчас, последние сверху." : "Открытых сессий нет."}
      columns={["Устройство", "Адрес", "Открыта", "Последнее использование"]}
      rows={sessions.map((session) => (
        <TableRow key={session.id}>
          <TableCell className="max-w-64 truncate ps-6" title={session.device_label ?? undefined}>
            {deviceName(session.device_label) ?? clientLabel(session.client_kind)}
          </TableCell>
          <TableCell className="font-mono text-xs">{session.ip ?? "—"}</TableCell>
          <TableCell className="tabular-nums">{formatDateTime(session.created_at, shown)}</TableCell>
          <TableCell className="pe-6 tabular-nums">{formatDateTime(session.last_used_at, shown)}</TableCell>
        </TableRow>
      ))}
    />
  );
}

/** Последние попытки входа и чем они кончились. */
export function SignInsCard({ signIns }: { signIns: UserCard["sign_ins"] }) {
  const shown = useDisplayZone();
  return (
    <ActivityCard
      title="Последние входы"
      description={signIns.length ? "Попытки входа, последние сверху." : "Попыток входа не было."}
      columns={["Когда", "Итог", "Откуда", "Адрес"]}
      rows={signIns.map((attempt) => (
        <TableRow key={`${attempt.created_at}-${attempt.outcome}`}>
          <TableCell className="ps-6 tabular-nums">{formatDateTime(attempt.created_at, shown)}</TableCell>
          <TableCell>{outcomeLabel(attempt.outcome)}</TableCell>
          <TableCell>{clientLabel(attempt.client_kind)}</TableCell>
          <TableCell className="pe-6 font-mono text-xs">{attempt.ip ?? "—"}</TableCell>
        </TableRow>
      ))}
    />
  );
}
