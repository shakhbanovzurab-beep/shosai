"use client";

import { useState } from "react";

import { RefreshCw } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import { applyFilter, DEFAULT_FILTER } from "../domain/list";
import { useWorkspaces, workspacesResource } from "../model/resources";
import { WorkspacesFilters } from "./workspaces-filters";
import { WorkspacesKpis } from "./workspaces-kpis";
import { WorkspacesTable } from "./workspaces-table";

function OverviewSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <span className="sr-only" role="status">
        Загрузка пространств…
      </span>
      <Skeleton className="h-32 rounded-xl" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}

/** The summary strip over the searchable list of every workspace. */
export function WorkspacesOverview() {
  const state = useWorkspaces();
  const [filter, setFilter] = useState(DEFAULT_FILTER);

  if (state.status === "loading") return <OverviewSkeleton />;
  if (state.status === "error")
    return (
      <LoadError
        title="Не удалось загрузить пространства"
        message={state.message}
        onRetry={() => void workspacesResource.refresh()}
        retryLabel="Повторить"
      />
    );

  const rows = state.data.workspaces;
  const plans = [...new Set(rows.map((w) => w.plan.name))].toSorted();
  const shown = applyFilter(rows, filter);
  return (
    <div className="flex flex-col gap-4">
      <WorkspacesKpis rows={rows} />
      <Card>
        <CardHeader className="border-b">
          <CardTitle>Все пространства</CardTitle>
          <CardDescription>
            Метаданные и счётчики. Содержимое встреч, файлов и задач администраторам не видно.
          </CardDescription>
          <CardAction>
            <Button
              variant="outline"
              size="sm"
              disabled={state.refreshing}
              onClick={() => void workspacesResource.refresh()}
            >
              <RefreshCw className={state.refreshing ? "motion-safe:animate-spin" : undefined} aria-hidden="true" />
              Обновить
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 px-0">
          <div className="px-4">
            <WorkspacesFilters filter={filter} plans={plans} onChange={setFilter} />
          </div>
          <WorkspacesTable rows={shown} onReset={() => setFilter({ ...DEFAULT_FILTER, sort: filter.sort })} />
        </CardContent>
      </Card>
    </div>
  );
}
