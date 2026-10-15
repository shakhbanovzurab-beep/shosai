import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { isNotFound } from "@/lib/api/errors";

import { type ExportJob, latestExport, requestExport } from "../api/account-data-api";

const EXPORT_KEY = ["identity", "export", "latest"] as const;
// Пока архив собирается, состояние спрашивается раз в 5 секунд; готовый или упавший — больше не опрашивается.
const POLL_MS = 5000;

async function latestOrNone(): Promise<ExportJob | null> {
  try {
    return await latestExport();
  } catch (error) {
    if (isNotFound(error)) return null;
    throw error;
  }
}

const inProgress = (job: ExportJob | null | undefined) => job?.state === "queued" || job?.state === "running";

/** Последняя выгрузка данных: null — ещё не просили; пока собирается — обновляется сама. */
export function useLatestExport() {
  return useQuery({
    queryKey: EXPORT_KEY,
    queryFn: latestOrNone,
    refetchInterval: (query) => (inProgress(query.state.data) ? POLL_MS : false),
  });
}

/** Попросить новую выгрузку; ответ сразу становится последней. */
export function useRequestExport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: requestExport,
    onSuccess: (job) => client.setQueryData(EXPORT_KEY, job),
  });
}
