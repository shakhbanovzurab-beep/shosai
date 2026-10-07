"use client";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { aiModelsResource } from "../model/ai-models-store";
import { ModelsTable } from "./models-table";
import { ProviderCard } from "./provider-card";
import { SpendChart } from "./spend-chart";
import { SpendKpis } from "./spend-kpis";
import { TopModels } from "./top-models";

const retry = () => void aiModelsResource.refresh();

export function AiModelsView() {
  const state = usePollingResource(aiModelsResource);

  if (state.status === "loading") return <AiModelsSkeleton />;
  if (state.status === "error")
    return (
      <LoadError
        title="Не удалось загрузить модели и расходы"
        message={state.message}
        onRetry={retry}
        retryLabel="Повторить"
      />
    );

  const { provider, spend, models } = state.data;
  return (
    <div className="flex flex-col gap-4" aria-busy={state.refreshing}>
      <div className="grid gap-4 xl:grid-cols-3">
        <ProviderCard provider={provider} />
        <div className="xl:col-span-2">
          <SpendKpis spend={spend} models={models} source={provider.source} />
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <SpendChart daily={spend.daily} />
        </div>
        <TopModels models={models} total={spend.month} />
      </div>
      <ModelsTable models={models} />
    </div>
  );
}

function AiModelsSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <span className="sr-only" role="status">
        Загрузка моделей и расходов…
      </span>
      <div className="grid gap-4 xl:grid-cols-3">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl xl:col-span-2" />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Skeleton className="h-80 rounded-xl xl:col-span-2" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}
