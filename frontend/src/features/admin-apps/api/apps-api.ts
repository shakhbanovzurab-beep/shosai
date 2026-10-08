import { apiRequest, jsonBody } from "@/lib/api/request";

import type { AppRelease, ReleaseMetadata, ReleasePatch, ReleasesResponse } from "../domain/contract";

const BASE = "/api/admin/apps/releases";
const at = (id: string) => `${BASE}/${encodeURIComponent(id)}`;

export type UploadProgress = { loaded: number; total: number };

/** The server's `{ detail }` message, or a generic one. */
function uploadError(xhr: XMLHttpRequest) {
  try {
    const body = JSON.parse(xhr.responseText) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Not JSON: fall through.
  }
  return xhr.status === 413 ? "Файл слишком большой." : `Не удалось загрузить сборку (${xhr.status || "нет связи"}).`;
}

/**
 * Sends the metadata and the build as multipart/form-data. XMLHttpRequest rather than fetch because
 * it reports upload progress everywhere; `signal` cancels the upload.
 */
function upload(file: File, metadata: ReleaseMetadata, onProgress: (p: UploadProgress) => void, signal: AbortSignal) {
  const form = new FormData();
  // Metadata first, so the server can reject a bad version before receiving the file.
  form.append("metadata", JSON.stringify(metadata));
  form.append("file", file, file.name);

  return new Promise<AppRelease>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", BASE);
    xhr.responseType = "text";
    xhr.upload.onprogress = (event) =>
      onProgress({ loaded: event.loaded, total: event.lengthComputable ? event.total : file.size });
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText) as AppRelease);
      else reject(new Error(uploadError(xhr)));
    };
    xhr.onerror = () => reject(new Error("Соединение прервалось. Проверьте сеть и попробуйте ещё раз."));
    xhr.onabort = () => reject(new DOMException("Загрузка отменена.", "AbortError"));
    signal.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}

export const appsApi = {
  list: () => apiRequest<ReleasesResponse>(BASE),
  upload,
  patch: (id: string, patch: ReleasePatch) => apiRequest<AppRelease>(at(id), jsonBody("PATCH", patch)),
  remove: (id: string) => apiRequest<void>(at(id), { method: "DELETE" }),
};
