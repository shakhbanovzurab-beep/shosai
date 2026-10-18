import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { PartLink } from "../domain/upload-parts";

export type UploadAnswer = components["schemas"]["UploadAnswer"];

const upload = (id: string) => ({ params: { path: { upload_id: id } } });
// Подпись части включает длину, но этот заголовок браузер ставит сам и не даёт задать.
const BROWSER_SET = new Set(["content-length", "host"]);

/** A part the bucket refused or never answered; `expired` when its signature ran out and a fresh link helps. */
export class PartFailedError extends Error {
  constructor(readonly expired: boolean) {
    super(expired ? "part link expired" : "part upload failed");
    this.name = "PartFailedError";
  }
}

/** Uploads straight to the home's bucket (FL-D1): `/v1/me/uploads*` signs each part for its exact length. */
export const uploadsApi = {
  create: (file: File): Promise<UploadAnswer> =>
    dataOf(
      apiClient.POST("/v1/me/uploads", {
        body: {
          purpose: "file_manager",
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
        },
      }),
    ),
  /** The parts done and fresh links for the rest: how an upload resumes. */
  read: (id: string): Promise<UploadAnswer> => dataOf(apiClient.GET("/v1/me/uploads/{upload_id}", upload(id))),
  complete: (id: string): Promise<UploadAnswer> =>
    dataOf(apiClient.POST("/v1/me/uploads/{upload_id}/complete", upload(id))),
  cancel: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/me/uploads/{upload_id}", upload(id))),
};

/**
 * PUTs one part's bytes to its signed link, reporting the bytes sent. XMLHttpRequest, not fetch: only it reports
 * upload progress. A signature that ran out answers 403, which a fresh link fixes.
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
