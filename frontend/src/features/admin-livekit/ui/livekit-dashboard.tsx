"use client";

import dynamic from "next/dynamic";

import { RefreshCw } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { formatClock } from "../domain/format";
import { overviewResource } from "../model/livekit-store";
import { EgressCard } from "./egress-card";
import { KpiStrip } from "./kpi-strip";
import { NodesCard } from "./nodes-card";
import { RoomsCard } from "./rooms-card";
import { ServerStatusCard } from "./server-status-card";

const CHARTS_SKELETON = (
  <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
    <Skeleton className="h-80 rounded-xl" />
    <Skeleton className="h-80 rounded-xl" />
  </div>
);

/** Recharts is heavy; the charts load after the rest of the dashboard. */
const HistoryCharts = dynamic(() => import("./history-charts").then((module) => module.HistoryCharts), {
  loading: () => CHARTS_SKELETON,
});

const refresh = () => void overviewResource.refresh();

const LOADING = (
  <div className="flex flex-col gap-4" aria-busy="true">
    <span className="sr-only">Загрузка данных LiveKit…</span>
    <Skeleton className="h-36 rounded-xl" />
    <Skeleton className="h-28 rounded-xl" />
    {CHARTS_SKELETON}
    <Skeleton className="h-56 rounded-xl" />
  </div>
);

export function LiveKitDashboard() {
  const state = usePollingResource(overviewResource);

  if (state.status === "loading") return LOADING;

  if (state.status === "error")
    return (
      <LoadError
        title="Не удалось получить данные LiveKit"
        message={state.message}
        onRetry={refresh}
        retryLabel="Повторить"
      />
    );

  const { data, refreshing } = state;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-end gap-3">
        <p className="text-muted-foreground text-sm tabular-nums" aria-live="polite">
          Обновлено в {formatClock(data.updated_at)} · каждые 10 секунд
        </p>
        <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
          <RefreshCw
            aria-hidden="true"
            className={refreshing ? "animate-spin motion-reduce:animate-none" : undefined}
          />
          Обновить
        </Button>
      </div>
      <ServerStatusCard server={data.server} updatedAt={data.updated_at} />
      <KpiStrip stats={data.stats} />
      <HistoryCharts history={data.history} />
      <NodesCard nodes={data.nodes} />
      <RoomsCard rooms={data.rooms} updatedAt={data.updated_at} />
      <EgressCard egress={data.egress} />
    </div>
  );
}
