import { type HubErrorCode, isHubErrorCode } from "../domain/errors";

/** A failed Hub request: the server's code (the client words it) and the HTTP status. */
export class HubApiError extends Error {
  constructor(
    readonly code: HubErrorCode,
    readonly status: number,
  ) {
    super(code);
    this.name = "HubApiError";
  }
}

/** The code behind any thrown value, for choosing the words to show. */
export const errorCode = (error: unknown): HubErrorCode => (error instanceof HubApiError ? error.code : "unknown");

function codeOf(body: unknown, status: number): HubErrorCode {
  const detail = (body as { detail?: unknown } | null)?.detail;
  const code = (detail as { code?: unknown } | null)?.code;
  if (isHubErrorCode(code)) return code;
  if (status === 404) return "not_found";
  if (status === 422) return "invalid";
  return "unknown";
}

/** Calls one of the Hub's `/api/*` routes; throws HubApiError with the server's code. */
export async function hubRequest<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store", ...init });
  } catch {
    throw new HubApiError("network", 0);
  }
  if (res.status === 204) return undefined as T;
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new HubApiError(codeOf(body, res.status), res.status);
  return body as T;
}

export const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});
