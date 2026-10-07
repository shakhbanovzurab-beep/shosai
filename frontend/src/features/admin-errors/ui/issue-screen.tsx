"use client";

import Link from "next/link";

import { ArrowLeft } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { formatFullDateTime, formatNumber, formatRelative } from "../domain/format";
import { getLastListSearch, issueResource } from "../model/errors-store";
import { IssueActions } from "./issue-actions";
import { IssueBreadcrumbs } from "./issue-breadcrumbs";
import { SeverityBadge, SourceLabel, StatusBadge } from "./issue-meta";
import { IssueSide } from "./issue-side";
import { RecentEvents } from "./recent-events";
import { StackTrace } from "./stack-trace";

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm tabular-nums">{children}</dd>
    </div>
  );
}

/** One issue: its header with actions, the stack, breadcrumbs, recent events and environment. */
export function IssueScreen({ id }: { id: string }) {
  const resource = issueResource(id);
  const state = usePollingResource(resource);
  const search = getLastListSearch();

  const back = (
    <Button variant="ghost" size="sm" className="-ml-2 w-fit" asChild>
      <Link href={search ? `/admin/errors?${search}` : "/admin/errors"}>
        <ArrowLeft aria-hidden="true" />
        Все ошибки
      </Link>
    </Button>
  );

  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-4" aria-busy="true">
        {back}
        <span className="sr-only" role="status">
          Загрузка ошибки…
        </span>
        <Skeleton className="h-28 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Skeleton className="h-96 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </div>
    );

  if (state.status === "error")
    return (
      <div className="flex flex-col gap-4">
        {back}
        <LoadError
          title="Не удалось открыть ошибку"
          message={state.message}
          onRetry={() => void resource.refresh()}
          retryLabel="Повторить"
        />
      </div>
    );

  const issue = state.data;
  return (
    <div className="flex flex-col gap-4">
      {back}
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={issue.severity} />
          <StatusBadge status={issue.status} />
          <SourceLabel source={issue.source} component={issue.platform_component} />
        </div>
        <h1 className="break-words font-semibold text-xl tracking-tight">{issue.title}</h1>
        <p className="break-all font-mono text-muted-foreground text-sm">{issue.culprit}</p>
        <dl className="flex flex-wrap gap-x-8 gap-y-3">
          <Stat label="События">{formatNumber(issue.event_count)}</Stat>
          <Stat label="Пользователи">{formatNumber(issue.user_count)}</Stat>
          <Stat label="Впервые">
            <time dateTime={issue.first_seen} title={formatFullDateTime(issue.first_seen)}>
              {formatRelative(issue.first_seen)}
            </time>
          </Stat>
          <Stat label="Последняя">
            <time dateTime={issue.last_seen} title={formatFullDateTime(issue.last_seen)}>
              {formatRelative(issue.last_seen)}
            </time>
          </Stat>
          <Stat label="Последняя версия">
            <span className="font-mono">{issue.latest_version}</span>
          </Stat>
          <Stat label="Исполнитель">{issue.assignee?.name ?? "Не назначен"}</Stat>
        </dl>
        <IssueActions issue={issue} />
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <StackTrace exceptionType={issue.exception_type} message={issue.message} frames={issue.stack} />
          <IssueBreadcrumbs breadcrumbs={issue.breadcrumbs} />
          <RecentEvents events={issue.recent_events} />
        </div>
        <IssueSide issue={issue} />
      </div>
    </div>
  );
}
