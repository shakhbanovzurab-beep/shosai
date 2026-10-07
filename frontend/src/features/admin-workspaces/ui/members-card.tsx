import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { AdminWorkspaceDetail } from "../domain/contract";
import { formatFullDateTime, formatNumber, formatRelative, plural } from "../domain/format";
import { ROLE_LABEL } from "../domain/labels";

/** Who is in the workspace, their role, how much they use it, and the invitations still open. */
export function MembersCard({ workspace: w }: { workspace: AdminWorkspaceDetail }) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>Участники</CardTitle>
        <CardDescription>
          {plural(w.members, ["участник", "участника", "участников"])}
          {w.invitations.length
            ? ` · ${plural(w.invitations.length, ["приглашение", "приглашения", "приглашений"])} ждут ответа`
            : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-4">Участник</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead className="hidden text-right md:table-cell">Встречи · мин за месяц</TableHead>
              <TableHead className="hidden pr-4 sm:table-cell">Активность</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {w.people.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="max-w-64 pl-4">
                  <span className="block truncate font-medium">{p.name}</span>
                  <span className="block truncate text-muted-foreground text-xs">{p.email}</span>
                </TableCell>
                <TableCell>
                  <span className="block">{ROLE_LABEL[p.role]}</span>
                  {p.teams ? (
                    <span className="block text-muted-foreground text-xs">
                      {plural(p.teams, ["команда", "команды", "команд"])}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="hidden text-right tabular-nums md:table-cell">
                  {formatNumber(p.meetings_month)} · {formatNumber(p.minutes_month)}
                </TableCell>
                <TableCell className="hidden pr-4 text-muted-foreground sm:table-cell">
                  {p.last_active_at ? (
                    <time dateTime={p.last_active_at} title={formatFullDateTime(p.last_active_at)}>
                      {formatRelative(p.last_active_at)}
                    </time>
                  ) : (
                    "входов не было"
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {w.invitations.length ? (
          <section aria-labelledby="admin-invitations" className="flex flex-col gap-2 px-4">
            <h3 id="admin-invitations" className="font-medium text-sm">
              Приглашения
            </h3>
            <ul className="flex flex-col gap-1 text-sm">
              {w.invitations.map((i) => (
                <li key={i.email} className="flex flex-wrap justify-between gap-x-4 text-muted-foreground">
                  <span className="truncate text-foreground">{i.email}</span>
                  <span>
                    {ROLE_LABEL[i.role].toLowerCase()} · отправлено {formatRelative(i.sent_at)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </CardContent>
    </Card>
  );
}
