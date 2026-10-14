import { ApiError } from "@/lib/api/errors";

import { type AuthProblem, authProblemOf } from "../domain/problems";

/** Отказ сервера словами интерфейса: причина, номер запроса для поддержки и сколько подождать, если сервер сказал. */
export interface Refusal {
  problem: AuthProblem;
  requestId: string | null;
  retryAfterSeconds: number | null;
}

export type Outcome<T> = { kind: "done"; value: T } | ({ kind: "refused" } & Refusal);

function retryAfterOf(error: ApiError): number | null {
  const seconds = error.params.retry_after_seconds;
  return typeof seconds === "number" && seconds > 0 ? seconds : null;
}

export function refusalOf(error: unknown): Refusal {
  if (error instanceof ApiError) {
    return { problem: authProblemOf(error.code), requestId: error.requestId, retryAfterSeconds: retryAfterOf(error) };
  }
  // Сеть или браузер: человек видит общую причину и пробует ещё раз.
  return { problem: "unknown", requestId: null, retryAfterSeconds: null };
}

/** Выполнить шаг входа и превратить отказ в причину, которую форма покажет словами. */
export async function attempt<T>(step: () => Promise<T>): Promise<Outcome<T>> {
  try {
    return { kind: "done", value: await step() };
  } catch (error) {
    return { kind: "refused", ...refusalOf(error) };
  }
}
