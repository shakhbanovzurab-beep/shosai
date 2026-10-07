"use client";

import type { ReactNode } from "react";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

const ROWS = ["a", "b", "c", "d"];

/** Table-shaped skeleton while loading, a retryable error, or the content once data is in. */
export function ResourceView<T>({
  state,
  errorTitle,
  onRetry,
  children,
}: {
  state: ResourceState<T>;
  errorTitle: string;
  onRetry: () => void;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-2 rounded-xl border p-4" aria-busy="true">
        <span className="sr-only">Загрузка…</span>
        <Skeleton className="h-8 w-full" />
        {ROWS.map((row) => (
          <Skeleton key={row} className="h-12 w-full" />
        ))}
      </div>
    );
  if (state.status === "error")
    return <LoadError title={errorTitle} message={state.message} onRetry={onRetry} retryLabel="Повторить" />;
  return children(state.data);
}
