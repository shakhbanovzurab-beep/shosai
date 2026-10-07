"use client";

import { useState } from "react";

import dynamic from "next/dynamic";

import { RefreshCw } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { IssuesResponse } from "../domain/contract";
import { ERROR_PERIODS } from "../domain/dimensions";
import { issuesResource } from "../model/errors-store";
import { useIssuesQuery } from "../model/use-issues-query";
import { ErrorsFilters } from "./errors-filters";
import { ErrorsKpis } from "./errors-kpis";
import { IssuesTable } from "./issues-table";

// The chart library loads with the timeline, after the rest of the screen.
const ErrorsTimeline = dynamic(() => import("./errors-timeline").then((module) => module.ErrorsTimeline), {
  loading: () => <Skeleton className="h-80 rounded-xl" />,
});

export function ErrorsOverviewSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <span className="sr-only" role="status">
        Загрузка ошибок…
      </span>
      <Skeleton className="h-36 rounded-xl" />
      <Skeleton className="h-80 rounded-xl" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}

/** KPIs, the events timeline and the filtered, paged issue list. */
export function ErrorsOverview() {
  const { query, setQuery } = useIssuesQuery();
  const resource = issuesResource(query);
  const state = usePollingResource(resource);

  // Keeps the last result on screen while another filter loads, instead of flashing a skeleton.
  const [shown, setShown] = useState<IssuesResponse | null>(null);
  if (state.status === "ready" && state.data !== shown) setShown(state.data);
  const data = state.status === "ready" ? state.data : shown;
  const busy = state.status === "loading" || (state.status === "ready" && state.refreshing);
  const periodLabel = ERROR_PERIODS.find((period) => period.id === query.period)?.label ?? "";

  if (!data) {
    if (state.status === "error")
      return (
        <LoadError
          title="Не удалось загрузить ошибки"
          message={state.message}
          onRetry={() => void resource.refresh()}
          retryLabel="Повторить"
        />
      );
    return <ErrorsOverviewSkeleton />;
  }

  return (
    <div className="flex flex-col gap-4">
      <ErrorsKpis kpis={data.kpis} />
      <ErrorsTimeline timeline={data.timeline} source={query.source} periodLabel={periodLabel} />
      <Card>
        <CardHeader className="border-b">
          <CardTitle>Ошибки</CardTitle>
          <CardDescription>Сгруппированы по отпечатку (fingerprint) — одна строка на одну причину</CardDescription>
          <CardAction>
            <Button variant="outline" size="sm" disabled={busy} onClick={() => void resource.refresh()}>
              <RefreshCw className={busy ? "motion-safe:animate-spin" : undefined} aria-hidden="true" />
              Обновить
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 px-0">
          <div className="px-4">
            <ErrorsFilters query={query} versions={data.versions} onChange={setQuery} />
          </div>
          {state.status === "error" ? (
            <p role="alert" className="px-4 text-destructive text-sm">
              Не удалось обновить список: {state.message}
            </p>
          ) : null}
          <div aria-busy={busy} className={busy ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <IssuesTable
              items={data.items}
              total={data.total}
              pageSize={data.page_size}
              query={query}
              onChange={setQuery}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
