import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";

const MAX_QUERY_RETRIES = 2;

// Повтор имеет смысл только для сбоя сети или сервера; ошибка запроса (4xx) повторится так же.
const isTransient = (error: unknown) => !(error instanceof ApiError) || error.status >= 500;

/** Единый кеш серверного состояния: запросы повторяются при временных сбоях, мутации — никогда. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => failureCount < MAX_QUERY_RETRIES && isTransient(error),
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
