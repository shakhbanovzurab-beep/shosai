"use client";

import type { ReactNode } from "react";

import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import type { ResourceState } from "@/lib/polling-resource";

/** A retryable error for a pane whose first load failed. */
export function PaneError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <Empty className="m-auto">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CircleAlert />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{message}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Повторить
        </Button>
      </EmptyContent>
    </Empty>
  );
}

/** The pane's skeleton while loading, a retryable error, or its content once the data is in. */
export function PaneState<T>({
  state,
  errorTitle,
  fallback,
  onRetry,
  children,
}: {
  state: ResourceState<T>;
  errorTitle: string;
  fallback: ReactNode;
  onRetry: () => void;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading") return fallback;
  if (state.status === "error") return <PaneError title={errorTitle} message={state.message} onRetry={onRetry} />;
  return children(state.data);
}
