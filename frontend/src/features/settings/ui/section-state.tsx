"use client";

import type { ReactNode } from "react";

import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

/** Loading skeleton, a retryable error, or the section's content once its data is in. */
export function SectionState<T>({
  state,
  onRetry,
  children,
}: {
  state: ResourceState<T>;
  onRetry: () => void;
  children: (data: T) => ReactNode;
}) {
  const t = useTranslations("settings");
  if (state.status === "loading") return <Skeleton className="h-48 rounded-xl" />;
  if (state.status === "error") return <LoadError title={t("loadFailed")} message={state.message} onRetry={onRetry} />;
  return children(state.data);
}
