"use client";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { PlatformPromptsProvider } from "../model/platform-prompts-provider";
import { platformPromptsResource } from "../model/platform-prompts-store";
import { PlatformPromptsHeader } from "./platform-prompts-header";
import { PlatformPromptsTabs } from "./platform-prompts-tabs";
import { UnpublishedBanner } from "./unpublished-banner";

function LoadingState() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <span className="sr-only" role="status">
        Загрузка настроек…
      </span>
      <Skeleton className="h-9 w-72 rounded-lg" />
      <Skeleton className="h-8 w-full max-w-xl rounded-lg" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}

/** Loads the platform configuration, then hands the draft to the editor. */
export function PlatformPromptsScreen() {
  const state = usePollingResource(platformPromptsResource);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl tracking-tight">Промты платформы</h1>
        <p className="text-muted-foreground text-sm">
          Глобальные настройки Leo для всех пользователей. Применяются раньше личного контекста из Studio.
        </p>
      </div>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? (
        <LoadError
          title="Не удалось загрузить промты платформы"
          message={state.message}
          onRetry={() => void platformPromptsResource.refresh()}
          retryLabel="Повторить"
        />
      ) : null}
      {state.status === "ready" ? (
        <PlatformPromptsProvider data={state.data}>
          <PlatformPromptsHeader />
          <UnpublishedBanner />
          <PlatformPromptsTabs />
        </PlatformPromptsProvider>
      ) : null}
    </div>
  );
}
