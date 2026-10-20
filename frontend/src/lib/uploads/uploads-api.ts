import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { PartLink } from "./upload-parts";

export type UploadAnswer = components["schemas"]["UploadAnswer"];
/** Для чего загрузка: для Файлового менеджера или для среза, который заберёт байты, например записи встречи. */
export type UploadPurpose = components["schemas"]["UploadPurpose"];

const upload = (id: string) => ({ params: { path: { upload_id: id } } });
// Подпись части включает длину, но этот заголовок браузер ставит сам и не даёт задать.
const BROWSER_SET = new Set(["content-length", "host"]);

/** Часть, которую бакет отверг или не принял; `expired` — подпись истекла, и поможет свежая ссылка. */
export class PartFailedError extends Error {
  constructor(readonly expired: boolean) {
    super(expired ? "part link expired" : "part upload failed");
    this.name = "PartFailedError";
  }
}

/** Загрузка прямо в бакет дома (FL-D1): `/v1/me/uploads*` подписывает каждую часть на её точную длину. */
export const uploadsApi = {
  create: (file: File, purpose: UploadPurpose): Promise<UploadAnswer> =>
    dataOf(
      apiClient.POST("/v1/me/uploads", {
        body: {
          purpose,
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
        },
      }),
    ),
  /** Готовые части и свежие ссылки на остальные: так загрузка продолжается. */
  read: (id: string): Promise<UploadAnswer> => dataOf(apiClient.GET("/v1/me/uploads/{upload_id}", upload(id))),
  complete: (id: string): Promise<UploadAnswer> =>
    dataOf(apiClient.POST("/v1/me/uploads/{upload_id}/complete", upload(id))),
  cancel: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/me/uploads/{upload_id}", upload(id))),
};

/**
 * Кладёт байты одной части по её подписанной ссылке и сообщает, сколько ушло. XMLHttpRequest, а не fetch: только
 * он сообщает о ходе отправки. Истёкшая подпись отвечает 403, и её чинит свежая ссылка.
 */
export function putPart(link: PartLink, body: Blob, onSent: (bytes: number) => void, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", link.url);
    for (const [name, value] of Object.entries(link.headers))
      if (!BROWSER_SET.has(name.toLowerCase())) request.setRequestHeader(name, value);
    request.upload.onprogress = (event) => onSent(event.loaded);
    request.onload = () =>
      request.status >= 200 && request.status < 300 ? resolve() : reject(new PartFailedError(request.status === 403));
    request.onerror = () => reject(new PartFailedError(false));
    request.onabort = () => reject(new PartFailedError(false));
    signal?.addEventListener("abort", () => request.abort(), { once: true });
    request.send(body);
  });
}
