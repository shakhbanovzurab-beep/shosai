/** FastAPI reports errors as `{ detail: string }`, or a list of validation errors on 422. */
function errorMessage(detail: unknown, status: number) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg).join("; ");
  // No words from the backend: a status code reads the same in every interface language.
  return `HTTP ${status}`;
}

/** A failed request: the backend's message, plus the HTTP status for callers that tell cases apart. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** True for a 404 from one of our routes, e.g. something deleted or not shared with the user. */
export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;

/** Fetches JSON from one of our `/api/*` routes, throwing an ApiError with the backend's message on failure. */
export async function apiRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (res.status === 204) return undefined as T;
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(errorMessage((body as { detail?: unknown } | null)?.detail, res.status), res.status);
  return body as T;
}

/** A JSON request body with the matching content type. */
export const jsonBody = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});
