"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, SearchX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/lib/navigation";

import type { ErrorIssue } from "../domain/contract";
import type { IssueSort } from "../domain/dimensions";
import { formatFullDateTime, formatNumber, formatRelative } from "../domain/format";
import type { IssuesQuery } from "../domain/query";
import { EmptyState } from "./empty-state";
import { SeverityBadge, SourceLabel, StatusBadge } from "./issue-meta";

type Props = {
  items: ErrorIssue[];
  total: number;
  pageSize: number;
  query: IssuesQuery;
  onChange: (patch: Partial<IssuesQuery>) => void;
};

function SortHeader({
  sort,
  label,
  query,
  onChange,
  className,
}: {
  sort: IssueSort;
  label: string;
  query: IssuesQuery;
  onChange: Props["onChange"];
  className?: string;
}) {
  const active = query.sort === sort;
  const ascending = query.order === "asc";
  let Icon = ArrowUpDown;
  let ariaSort: "ascending" | "descending" | "none" = "none";
  if (active) {
    Icon = ascending ? ArrowUp : ArrowDown;
    ariaSort = ascending ? "ascending" : "descending";
  }
  return (
    <TableHead className={className} aria-sort={ariaSort}>
      <Button
        variant="ghost"
        size="sm"
        className="-ml-2 h-7 px-2 font-normal"
        onClick={() => onChange({ sort, order: active && query.order === "desc" ? "asc" : "desc" })}
      >
        {label}
        <Icon aria-hidden="true" className={active ? undefined : "text-muted-foreground"} />
      </Button>
    </TableHead>
  );
}

function TimeCell({ iso }: { iso: string }) {
  return (
    <time dateTime={iso} title={formatFullDateTime(iso)} className="whitespace-nowrap">
      {formatRelative(iso)}
    </time>
  );
}

export function IssuesTable({ items, total, pageSize, query, onChange }: Props) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const page = Math.min(query.page, pageCount);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  if (total === 0)
    return (
      <EmptyState
        icon={<SearchX />}
        title="Ошибок не найдено"
        description="За выбранный период нет ошибок с такими фильтрами. Попробуйте расширить период или сбросить фильтры."
      />
    );

  return (
    <div className="flex flex-col gap-4">
      <Table className="**:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4">
        <TableHeader className="[&_tr]:border-t">
          <TableRow>
            <TableHead className="min-w-80 font-normal">Ошибка</TableHead>
            <TableHead className="font-normal">Источник</TableHead>
            <SortHeader sort="first_seen" label="Впервые" query={query} onChange={onChange} />
            <SortHeader sort="last_seen" label="Последняя" query={query} onChange={onChange} />
            <SortHeader sort="events" label="События" query={query} onChange={onChange} className="text-right" />
            <SortHeader sort="users" label="Польз." query={query} onChange={onChange} className="text-right" />
            <TableHead className="font-normal">Версия</TableHead>
            <TableHead className="font-normal">Статус</TableHead>
            <TableHead className="font-normal">Исполнитель</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((issue) => (
            <TableRow key={issue.id} className="relative border-border/60 has-[a:focus-visible]:bg-muted/50">
              <TableCell className="max-w-md whitespace-normal py-3">
                <div className="flex flex-col gap-1.5">
                  <Link
                    href={`/admin/errors/${issue.id}`}
                    className="line-clamp-2 font-medium outline-none after:absolute after:inset-0 hover:underline"
                  >
                    {issue.title}
                  </Link>
                  <div className="flex min-w-0 items-center gap-2">
                    <SeverityBadge severity={issue.severity} />
                    <span className="truncate font-mono text-muted-foreground text-xs">{issue.culprit}</span>
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <SourceLabel source={issue.source} component={issue.platform_component} />
              </TableCell>
              <TableCell className="text-muted-foreground">
                <TimeCell iso={issue.first_seen} />
              </TableCell>
              <TableCell>
                <TimeCell iso={issue.last_seen} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{formatNumber(issue.event_count)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatNumber(issue.user_count)}</TableCell>
              <TableCell className="font-mono text-xs">{issue.latest_version}</TableCell>
              <TableCell>
                <StatusBadge status={issue.status} />
              </TableCell>
              <TableCell className="whitespace-nowrap">
                {issue.assignee ? issue.assignee.name : <span className="text-muted-foreground">Не назначен</span>}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <nav aria-label="Страницы" className="flex flex-wrap items-center justify-between gap-3 px-4">
        <p className="text-muted-foreground text-sm tabular-nums">
          {formatNumber(from)}–{formatNumber(to)} из {formatNumber(total)}
        </p>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-sm tabular-nums">
            Страница {page} из {pageCount}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Предыдущая страница"
            disabled={page <= 1}
            onClick={() => onChange({ page: page - 1 })}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Следующая страница"
            disabled={page >= pageCount}
            onClick={() => onChange({ page: page + 1 })}
          >
            <ChevronRight />
          </Button>
        </div>
      </nav>
    </div>
  );
}
