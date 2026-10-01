// Ответ браузера на запрос камеры и микрофона. По умолчанию стенд даёт
// поддельное устройство без запроса (determinism/browser-flags.ts); состояние
// может показать отказ пользователя или запрос, который ещё ждёт ответа.

import type { BrowserContext } from "@playwright/test";

/** denied — пользователь запретил доступ; pending — окно разрешения ещё открыто. */
export type MediaAccess = "denied" | "pending";

export async function installMediaAccess(context: BrowserContext, access: MediaAccess | undefined): Promise<void> {
  if (access === undefined) return;
  await context.addInitScript((mode: MediaAccess) => {
    const devices = navigator.mediaDevices as MediaDevices | undefined;
    if (devices === undefined) return;
    devices.getUserMedia = async (): Promise<MediaStream> =>
      mode === "denied"
        ? Promise.reject(new DOMException("Permission denied", "NotAllowedError"))
        : new Promise<MediaStream>(() => undefined);
  }, access);
}
