"use client";

import type { ReactNode } from "react";

import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import type { ResourceState } from "@/lib/polling-resource";

/** A retryable error for a block that failed its first load. */
export function BillingError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <Empty className="border border-dashed" role="alert">
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

/** The fallback while loading, a retryable error, or the content once the data is in. */
export function BillingState<T>({
  state,
  fallback,
  errorTitle,
  onRetry,
  children,
}: {
  state: ResourceState<T>;
  fallback: ReactNode;
  errorTitle: string;
  onRetry: () => void;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading") return fallback;
  if (state.status === "error") return <BillingError title={errorTitle} message={state.message} onRetry={onRetry} />;
  return children(state.data);
}
