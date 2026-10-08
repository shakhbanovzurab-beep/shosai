/**
 * Неудачный запрос. Бэкенд отвечает на ошибки конвертом ADR 0008:
 * `{ "error": { code, request_id, params?, fields? }, "detail": … }`; маршруты для выпущенных клиентов и моки
 * разработки отвечают `{ "detail": "<сообщение>" }` или списком ошибок валидации. Здесь читаются оба вида.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null = null,
    readonly requestId: string | null = null,
    readonly params: Readonly<Record<string, unknown>> = {},
    readonly fields: Readonly<Record<string, string>> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Id запроса стоит показать для поддержки: сбой сервера или код, для которого в интерфейсе нет слов. */
  get showsRequestId(): boolean {
    return this.requestId !== null && (this.status >= 500 || this.message === this.code);
  }
}

interface Envelope {
  error?: { code?: unknown; request_id?: unknown; params?: unknown; fields?: unknown };
  detail?: unknown;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

// Текст ошибки: строка `detail`, сообщения ошибок валидации или код; без слов от сервера — статус.
function messageOf(body: Envelope | null, code: string | null, status: number): string {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: { msg?: unknown }) => String(item.msg ?? "")).join("; ");
  if (isRecord(detail) && typeof detail.code === "string") return detail.code;
  return code ?? `HTTP ${status}`;
}

/** ApiError неудачного ответа — по телу и заголовку `X-Request-ID`. */
export function apiErrorOf(status: number, body: unknown, headers?: Headers): ApiError {
  const envelope = isRecord(body) ? (body as Envelope) : null;
  const error = isRecord(envelope?.error) ? envelope.error : undefined;
  const code = typeof error?.code === "string" ? error.code : null;
  const requestId = typeof error?.request_id === "string" ? error.request_id : (headers?.get("x-request-id") ?? null);
  const params = isRecord(error?.params) ? error.params : {};
  const fields = isRecord(error?.fields) ? (error.fields as Record<string, string>) : {};
  return new ApiError(messageOf(envelope, code, status), status, code, requestId, params, fields);
}

/** True для 404: например, объект удалён или не доступен пользователю. */
export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;
