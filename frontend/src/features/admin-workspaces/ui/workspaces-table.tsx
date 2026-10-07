"use client";

import Link from "next/link";

import { SearchX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { AdminWorkspace } from "../domain/contract";
import { formatFullDateTime, formatMoney, formatNumber, formatRelative } from "../domain/format";
import { SeatsMeter } from "./seats-meter";
import { StatusBadge } from "./status-badge";

const workspaceHref = (id: string) => `/admin/workspaces/${encodeURIComponent(id)}`;

function Activity({ workspace }: { workspace: AdminWorkspace }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="tabular-nums">{formatNumber(workspace.minutes_month)} мин</span>
      <span className="text-muted-foreground text-xs">
        {workspace.last_active_at ? (
          <time dateTime={workspace.last_active_at} title={formatFullDateTime(workspace.last_active_at)}>
            {formatRelative(workspace.last_active_at)}
          </time>
        ) : (
          "ещё не открывали"
        )}
      </span>
    </div>
  );
}

/** One row per workspace; the name opens its page. */
export function WorkspacesTable({ rows, onReset }: { rows: AdminWorkspace[]; onReset: () => void }) {
  if (rows.length === 0)
    return (
      <Empty className="mx-4 mb-4 border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <SearchX />
          </EmptyMedia>
          <EmptyTitle>Ничего не найдено</EmptyTitle>
          <EmptyDescription>Под эти условия не подходит ни одно пространство.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button variant="outline" size="sm" onClick={onReset}>
            Сбросить фильтры
          </Button>
        </EmptyContent>
      </Empty>
    );

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="pl-4">Пространство</TableHead>
          <TableHead className="hidden lg:table-cell">Владелец</TableHead>
          <TableHead>Места</TableHead>
          <TableHead className="hidden md:table-cell">Активность за месяц</TableHead>
          <TableHead className="hidden sm:table-cell">Статус</TableHead>
          <TableHead className="hidden pr-4 text-right xl:table-cell">В месяц</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((w) => (
          <TableRow key={w.id} className="relative">
            <TableCell className="max-w-64 pl-4">
              {/* Stretched over the row, so a click anywhere opens the workspace. */}
              <Link
                href={workspaceHref(w.id)}
                className="block truncate font-medium outline-none after:absolute after:inset-0 focus-visible:underline"
              >
                {w.name}
              </Link>
              <span className="block truncate text-muted-foreground text-xs">
                {w.slug} · {w.plan.name}
              </span>
              {/* The status column is hidden on phones; it matters too much to drop. */}
              <span className="mt-1 block sm:hidden">
                <StatusBadge status={w.status} />
              </span>
            </TableCell>
            <TableCell className="hidden max-w-56 lg:table-cell">
              {w.owner ? (
                <>
                  <span className="block truncate">{w.owner.name}</span>
                  <span className="block truncate text-muted-foreground text-xs">{w.owner.email}</span>
                </>
              ) : (
                <span className="text-muted-foreground">Нет владельца</span>
              )}
            </TableCell>
            <TableCell>
              <SeatsMeter used={w.seats_used} seats={w.plan.seats} />
            </TableCell>
            <TableCell className="hidden md:table-cell">
              <Activity workspace={w} />
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <StatusBadge status={w.status} />
            </TableCell>
            <TableCell className="hidden pr-4 text-right tabular-nums xl:table-cell">
              {formatMoney(w.monthly_cents, w.plan.currency)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
