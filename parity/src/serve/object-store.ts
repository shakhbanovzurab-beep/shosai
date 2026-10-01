// Подставное хранилище объектов: то, куда ведут подписанные ссылки S3.
//
// Просмотр картинки, PDF, видео и звука в «Файлах» берёт у API подписанную
// ссылку и открывает её в браузере. У стенда записи S3 нет, поэтому ссылку
// задаёт состояние (synthetic download-url), а объект отдаёт этот модуль.
// Видео и звука здесь нет: в браузере стенда (Chromium headless shell) нет
// кодеков H.264 и AAC, и плеер обеих целей одинаково остаётся без кадра —
// снимается каркас плеера. Неизвестный объект получает 404, как в S3.

import { acmeLogoPng, priceListPdf } from "../samples/images.ts";

export const OBJECT_STORE_ORIGIN = "http://objects.parity.localhost";

export interface StoredObject {
  readonly contentType: string;
  readonly body: Buffer;
}

const OBJECTS: ReadonlyMap<string, () => StoredObject> = new Map([
  ["/acme/logo.png", () => ({ contentType: "image/png", body: acmeLogoPng() })],
  ["/price-2025.pdf", () => ({ contentType: "application/pdf", body: priceListPdf() })],
]);

/** Адрес объекта, который состояние отдаёт в ответе download-url. */
export function objectUrl(key: string): string {
  return `${OBJECT_STORE_ORIGIN}${key}`;
}

/** Объект по адресу запроса браузера или null (404). */
export function storedObject(url: URL): StoredObject | null {
  return OBJECTS.get(url.pathname)?.() ?? null;
}
