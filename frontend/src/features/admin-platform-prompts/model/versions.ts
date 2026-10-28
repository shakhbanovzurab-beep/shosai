import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { platformPromptsApi } from "../api/platform-prompts-api";
import type { VersionSummary } from "../domain/contract";

/** Ключ истории публикаций: публикация и откат перечитывают её. */
export const VERSIONS_KEY = ["admin", "platform-prompts", "versions"] as const;

/** Версии, новые сверху, страницами по курсору; конфигурации в списке нет. */
export function useVersions() {
  const query = useInfiniteQuery({
    queryKey: VERSIONS_KEY,
    queryFn: ({ pageParam }) => platformPromptsApi.versions(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
  const versions: VersionSummary[] = query.data?.pages.flatMap((page) => page.items) ?? [];
  return { ...query, versions };
}

/** Версия целиком — для сравнения. Опубликованная версия не меняется, поэтому прочитанная не устаревает. */
export function useVersion(id: string | null) {
  return useQuery({
    queryKey: ["admin", "platform-prompts", "version", id],
    queryFn: () => platformPromptsApi.version(id as string),
    enabled: id !== null,
    staleTime: Number.POSITIVE_INFINITY,
  });
}
